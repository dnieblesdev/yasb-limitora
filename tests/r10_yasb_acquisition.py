"""Ephemeral, verified R10 acquisition with bounded fail-closed cleanup."""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from tests.r10_yasb_manifest import load_manifest, validate_manifest

MAX_TRANSFER_BYTES = 512 * 1024 * 1024
MAX_EXPECTED_FILES = 60
CHUNK_BYTES = 1024 * 1024
REPARSE_POINT = 0x400
NOTE = "R10 cleanup failed; see cleanup_evidence."
Residue = Literal["absent", "present", "unknown"]


@dataclass(frozen=True, slots=True)
class CleanupEvidence:
    schema: Literal["r10-cleanup-evidence/v1"]; operation: str; entry_kind: str; residue: Residue
    preflight_complete: bool; expected_files: int; expected_directories: int
    observed_files: int; removed_files: int; removed_directories: int


class ArtifactCleanupError(RuntimeError):
    def __init__(self, evidence: CleanupEvidence):
        super().__init__("R10 artifact cleanup failed")
        self.evidence = evidence
        _attach(self, evidence)


class _CleanupFailure(Exception):
    def __init__(self, cause: BaseException):
        super().__init__(); self.cause = cause


@dataclass
class _CleanupState:
    expected_files: int
    expected_directories: int = 3; observed_files: int = 0; removed_files: int = 0; removed_directories: int = 0
    operation: str = "preflight"; entry_kind: str = "root"; residue: Residue = "unknown"; preflight_complete: bool = False

    def evidence(self) -> CleanupEvidence:
        return CleanupEvidence(
            "r10-cleanup-evidence/v1", self.operation, self.entry_kind, self.residue,
            self.preflight_complete, self.expected_files, self.expected_directories,
            self.observed_files, self.removed_files, self.removed_directories,
        )


def _attach(error: BaseException, evidence: CleanupEvidence) -> None:
    if not hasattr(error, "cleanup_evidence"):
        error.cleanup_evidence = evidence
    notes = getattr(error, "__notes__", None)
    notes = [] if notes is None else list(notes)
    if NOTE not in notes:
        add_note = getattr(error, "add_note", None)
        if callable(add_note):
            error.__notes__ = notes
            add_note(NOTE)
            notes = list(getattr(error, "__notes__", notes))
        else:
            notes.append(NOTE)
    notes = [note for note in notes if note != NOTE]
    notes.append(NOTE)
    error.__notes__ = notes


def _classify(path: Path, info: os.stat_result) -> str:
    attributes = getattr(info, "st_file_attributes", 0)
    if stat.S_ISLNK(info.st_mode): return "symlink"
    if attributes & REPARSE_POINT: return "reparse"
    if stat.S_ISDIR(info.st_mode): return "directory"
    if stat.S_ISREG(info.st_mode): return "file"
    return "nonregular"


def _lstat(path: Path) -> os.stat_result | None:
    return path.lstat()


def _failure(state: _CleanupState, operation: str, kind: str, residue: Residue, cause: BaseException) -> None:
    state.operation, state.entry_kind, state.residue = operation, kind, residue
    raise _CleanupFailure(cause) from cause


def _checked(state: _CleanupState, path: Path, operation: str, expected: str, missing: Residue = "unknown") -> os.stat_result:
    try:
        info = _lstat(path)
    except FileNotFoundError as cause:
        _failure(state, operation, "missing", missing, cause)
    except Exception as cause:
        _failure(state, operation, expected, "unknown", cause)
    kind = _classify(path, info)
    if kind != expected: _failure(state, operation, kind, "present", ValueError())
    return info


def _remove(state: _CleanupState, path: Path, kind: str, directory: bool = False) -> None:
    operation = "rmdir" if directory else "unlink"
    state.operation, state.entry_kind, state.residue = operation, kind, "unknown"
    _checked(state, path, operation, "directory" if directory else "file")
    try:
        (path.rmdir if directory else path.unlink)()
    except FileNotFoundError as cause:
        _failure(state, operation, kind, "unknown", cause)
    except Exception as cause:
        _failure(state, operation, kind, "unknown", cause)
    try: remaining = _lstat(path)
    except FileNotFoundError: return
    except Exception as cause: _failure(state, "postcondition", kind, "unknown", cause)
    if remaining is not None:
        _failure(state, "postcondition", kind, "present", ValueError())


def _scan(state: _CleanupState, directory: Path, expected: dict[Path, tuple[str, str]]) -> list[tuple[Path, str]]:
    paths = {path for path in expected if path.parent.name == directory.name}
    allowed = {path.name for path in paths} | {f"{path.name}.part" for path in paths}
    try: children = tuple(directory.iterdir())
    except Exception as cause: _failure(state, "preflight", "directory", "unknown", cause)
    plan, seen = [], set()
    for child in children:
        if child.name not in allowed: _failure(state, "preflight", "unexpected", "present", ValueError())
        _checked(state, child, "preflight", "file", "present")
        base = child.with_name(child.name.removesuffix(".part"))
        if base in seen: _failure(state, "preflight", "duplicate", "present", ValueError())
        seen.add(base)
        plan.append((child, "partial" if child.name.endswith(".part") else "file"))
        state.observed_files += 1
    return plan


def _expected_entries(manifest: dict) -> dict[Path, tuple[str, str]]:
    entries: dict[Path, tuple[str, str]] = {}
    for item in manifest["artifacts"]:
        entries[Path("wheelhouse", item["filename"])] = (item["url"], item["sha256"])
    for item in manifest["sources"]:
        relative = Path("sources", f"{item['name']}.tar.gz")
        if relative in entries:
            raise ValueError("manifest contains duplicate artifact paths")
        entries[relative] = (item["archive_url"], item["archive_sha256"])
    if not 0 < len(entries) <= MAX_EXPECTED_FILES: raise ValueError("manifest entry count exceeds cleanup bound")
    return entries


def _trusted_temp_parent() -> Path:
    parent = Path(tempfile.gettempdir())
    try:
        info = parent.lstat()
    except OSError as error:
        raise ValueError("OS temp parent is unavailable") from error
    if (not parent.is_absolute() or stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & REPARSE_POINT
            or not stat.S_ISDIR(info.st_mode) or not os.access(parent, os.W_OK | os.X_OK)):
        raise ValueError("OS temp parent is not a trusted directory")
    return parent


def _download(url: str, target: Path, expected: str, opener=urllib.request.urlopen) -> None:
    partial = target.with_name(f"{target.name}.part")
    digest, size = hashlib.sha256(), 0
    with opener(url, timeout=60) as response:
        if getattr(response, "geturl", lambda: url)() != url: raise ValueError("artifact URL redirect mismatch")
        length = getattr(getattr(response, "headers", None), "get", lambda *_: None)("Content-Length")
        if length is not None and int(length) > MAX_TRANSFER_BYTES: raise ValueError("artifact exceeds transfer bound")
        with partial.open("xb") as output:
            while chunk := response.read(CHUNK_BYTES):
                size += len(chunk)
                if size > MAX_TRANSFER_BYTES: raise ValueError("artifact exceeds transfer bound")
                digest.update(chunk)
                output.write(chunk)
    if digest.hexdigest() != expected: raise ValueError("artifact hash mismatch")
    try:
        target.lstat()
    except FileNotFoundError:
        pass
    else: raise ValueError("artifact destination already exists")
    partial.rename(target)


def _cleanup(bundle: Path, expected: dict[Path, tuple[str, str]]) -> CleanupEvidence:
    state = _CleanupState(len(expected))
    try:
        state.operation, state.entry_kind = "preflight", "root"
        try:
            root_info = _lstat(bundle)
        except FileNotFoundError:
            state.residue = "absent"
            state.preflight_complete = True
            return state.evidence()
        except Exception as cause:
            _failure(state, "preflight", "root", "unknown", cause)
        root_kind = _classify(bundle, root_info)
        if root_kind != "directory":
            _failure(state, "preflight", root_kind, "present", ValueError())

        directories = (bundle / "wheelhouse", bundle / "sources")
        try: root_children = tuple(bundle.iterdir())
        except Exception as cause: _failure(state, "preflight", "root", "unknown", cause)
        if {child.name for child in root_children} != {path.name for path in directories}:
            _failure(state, "preflight", "unexpected", "present", ValueError())
        for child in root_children: _checked(state, child, "preflight", "directory", "present")
        plan: list[tuple[Path, str]] = []
        for directory in directories:
            state.entry_kind = "directory"
            _checked(state, directory, "preflight", "directory", "present")
            plan.extend(_scan(state, directory, expected))
        state.preflight_complete = True
        state.residue = "present"
        for path, kind in plan:
            _remove(state, path, kind)
            state.removed_files += 1
        for directory in (*directories, bundle):
            _remove(state, directory, "directory", directory=True)
            state.removed_directories += 1
        state.residue = "absent"
        return state.evidence()
    except _CleanupFailure as failure:
        evidence = state.evidence()
        cleanup_error = ArtifactCleanupError(evidence)
        raise cleanup_error from failure.cause
    except BaseException as failure:
        _attach(failure, state.evidence())
        raise


@contextmanager
def acquire_artifact_bundle(*, manifest: dict | None = None, opener=urllib.request.urlopen):
    """Yield one verified private bundle and remove it on every exit path."""
    manifest = load_manifest() if manifest is None else manifest
    validate_manifest(manifest)
    expected = _expected_entries(manifest)
    bundle: Path | None = None
    try:
        bundle = Path(tempfile.mkdtemp(prefix="yasb-r10-", dir=_trusted_temp_parent()))
        (bundle / "wheelhouse").mkdir()
        (bundle / "sources").mkdir()
        for relative, (url, digest) in expected.items():
            _download(url, bundle / relative, digest, opener)
        yield bundle
    except BaseException as primary:
        if bundle is not None:
            try:
                _cleanup(bundle, expected)
            except BaseException as cleanup_failure:
                evidence = getattr(cleanup_failure, "cleanup_evidence", None)
                if evidence is not None:
                    _attach(primary, evidence)
        raise
    else:
        if bundle is not None:
            _cleanup(bundle, expected)
