from __future__ import annotations

import ctypes, json, os, shutil, subprocess, tempfile
from pathlib import Path
import pytest
from tests import r10_yasb_acquisition as acquisition


_REPARSE_POINT = 0x400
_INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
_SHELL_METACHARACTERS = frozenset(";&|<>^()\"%!$`\n\r")
_EVIDENCE_FIELDS = ("schema", "junction", "reparse_attribute", "rejected_before_mutation", "sentinel_unchanged", "selected_tests", "skips")
_EVIDENCE_ENV = "R10_ACQUISITION_NATIVE_EVIDENCE_PATH"
def _validate_cmd_path(path: Path) -> None:
    value = str(path)
    if not value or any(character in value for character in _SHELL_METACHARACTERS):
        raise ValueError("unsafe junction path")
def _create_junction(link: Path, target: Path) -> None:
    _validate_cmd_path(link)
    _validate_cmd_path(target)
    subprocess.run(
        ["cmd.exe", "/d", "/s", "/c", "mklink", "/J", str(link), str(target)],
        check=True,
        capture_output=True,
        text=True,
        shell=False,
    )
def _get_file_attributes(path: Path) -> int:
    if os.name != "nt":
        raise AssertionError("native Windows is required")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_file_attributes = kernel32.GetFileAttributesW
    get_file_attributes.argtypes = [ctypes.c_wchar_p]
    get_file_attributes.restype = ctypes.c_uint32
    attributes = get_file_attributes(str(path))
    if attributes == _INVALID_FILE_ATTRIBUTES:
        error = ctypes.get_last_error()
        raise OSError(error, "GetFileAttributesW failed")
    return int(attributes)
def _native_evidence() -> dict[str, object]:
    return {
        "schema": "r10-acquisition-native/v1",
        "junction": True,
        "reparse_attribute": True,
        "rejected_before_mutation": True,
        "sentinel_unchanged": True,
        "selected_tests": 1,
        "skips": 0,
    }
def _write_native_evidence(path: Path) -> None:
    document = _native_evidence()
    assert tuple(document) == _EVIDENCE_FIELDS
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(document, separators=(",", ":")) + "\n")
def _teardown_sandbox(sandbox: Path, junction: Path) -> None:
    if os.path.lexists(junction):
        junction.rmdir()
        assert not os.path.lexists(junction)
    if os.path.lexists(sandbox):
        shutil.rmtree(sandbox)
    assert not os.path.lexists(sandbox)
@pytest.mark.parametrize("bad_path", ("link", "target"))
def test_cmd_path_rejects_metacharacters_before_spawn(monkeypatch, tmp_path, bad_path):
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: pytest.fail("spawned"))
    link = tmp_path / ("bad&path" if bad_path == "link" else "link")
    target = tmp_path / ("bad&path" if bad_path == "target" else "target")
    with pytest.raises(ValueError, match="unsafe junction path"):
        _create_junction(link, target)


@pytest.mark.skipif(os.name != "nt", reason="native junction proof requires Windows")
def test_real_junction_rejected_before_mutation():
    sandbox = Path(tempfile.mkdtemp(prefix="yasb-r10-native-"))
    external = sandbox / "external"
    bundle = sandbox / "bundle"
    junction = bundle / "wheelhouse"
    sentinel = external / "sentinel.bin"
    evidence_path = Path(os.environ[_EVIDENCE_ENV]) if os.environ.get(_EVIDENCE_ENV) else sandbox / "native-evidence.json"
    try:
        external.mkdir()
        bundle.mkdir()
        (bundle / "sources").mkdir()
        sentinel_bytes = b"external-sentinel"
        sentinel.write_bytes(sentinel_bytes)
        _create_junction(junction, external)
        junction_created = os.path.lexists(junction)
        attributes = _get_file_attributes(junction)
        reparse_attribute = bool(attributes & _REPARSE_POINT)
        assert junction_created and reparse_attribute

        visited, mutations = [], []
        original_iterdir = Path.iterdir
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(Path, "iterdir", lambda path: (visited.append(path) or original_iterdir(path)))
            patch.setattr(Path, "unlink", lambda path: (mutations.append(path) or path))
            patch.setattr(Path, "rmdir", lambda path: (mutations.append(path) or path))
            with pytest.raises(acquisition.ArtifactCleanupError):
                acquisition._cleanup(
                    bundle,
                    {Path("wheelhouse/artifact.whl"): ("", ""), Path("sources/source.tar.gz"): ("", "")},
                )
        rejected_before_mutation = (
            not any(path == external or path == junction for path in visited)
            and not mutations
            and os.path.lexists(junction)
        )
        sentinel_unchanged = sentinel.read_bytes() == sentinel_bytes
        assert rejected_before_mutation and sentinel_unchanged
        _write_native_evidence(evidence_path)
    finally:
        _teardown_sandbox(sandbox, junction)
