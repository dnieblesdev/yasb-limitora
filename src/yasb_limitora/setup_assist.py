"""Private setup-assist sentinel protocol and nonce-derived temp transport.

Internal module: no public export, no __all__. Dispatched from cli.main after
freeze_support() and before argv validation only when setup.exe's per-run nonce env
value is present; otherwise the sentinel falls through to invalid-argv exit 2 touching
nothing. Both sides independently derive %LOCALAPPDATA%\\Temp\\yasb-limitora-setup-assist\\
<nonce>\\ from the Local AppData known folder, fixed literal segments, and the validated
nonce; no request-supplied transport/target path is accepted; the sanitized result
travels only in the exclusively created, <=64 KiB result.json, never on stdout.
"""

from __future__ import annotations

import ctypes
import json
import ntpath
import os
import re
import stat
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

from . import _env_block, discovery
from .discovery import FsView, _canonical_local_dir, _components_safe

_SETUP_ASSIST_FLAG = "--__yasb-limitora-setup-assist"
_NONCE_ENV = "_YASB_SETUP_ASSIST_NONCE"
_NONCE = re.compile(r"[0-9a-f]{32}")
_REQUEST_SCHEMA = "gentle-ai.yasb-limitora.setup-assist-request/v1"
_RESULT_SCHEMA = "gentle-ai.yasb-limitora.setup-assist-result/v1"
_TRANSPORT_SEGMENTS = ("Temp", "yasb-limitora-setup-assist")
_ALLOWED_OPERATIONS = frozenset({"discover", "yasb-running", "path-add", "path-remove", "env-block-apply", "config-apply", "state-cleanup"})
_PATH_KEY = re.compile(r"path|dir|target|file|location|root|drive", re.IGNORECASE)
_MAX_OPERATIONS, _MAX_FILE_BYTES, _O_BINARY = 8, 64 * 1024, getattr(os, "O_BINARY", 0)
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

class _GUID(ctypes.Structure):
    _fields_ = [("data1", ctypes.c_uint32), ("data2", ctypes.c_uint16), ("data3", ctypes.c_uint16), ("data4", ctypes.c_uint8 * 8)]

def resolve_local_appdata() -> str | None:
    """Resolve Local AppData through the Windows known-folder API; None on any failure."""
    if os.name != "nt":
        return None
    try:
        shell32, ole32 = ctypes.WinDLL("shell32", use_last_error=True), ctypes.WinDLL("ole32")
        folder = _GUID(0xF1B32785, 0x6FBA, 0x4FCF, (ctypes.c_uint8 * 8)(0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91))
        out = ctypes.c_wchar_p()
        if shell32.SHGetKnownFolderPath(ctypes.byref(folder), 0, None, ctypes.byref(out)) != 0:
            return None
        try:
            return out.value or None
        finally:
            ole32.CoTaskMemFree(out)
    except OSError:
        return None

def _valid_nonce(value: object) -> bool:
    return isinstance(value, str) and _NONCE.fullmatch(value) is not None

def _expected_final(path: str) -> str:
    return ("\\\\?\\" + path).casefold()

def _handle_final_path(fd: int) -> str | None:
    """True Win32 final path of an already-open fd with every reparse point resolved; None on failure.

    Prechecks race: a validated nonce directory can be swapped for a junction between the
    component/kind validation and the pathname-based open. Revalidating through the handle
    itself binds each I/O to the location actually reached, never to a stale pathname view.
    """
    if os.name != "nt":
        return None
    try:
        import msvcrt
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        buffer = ctypes.create_unicode_buffer(32768)
        length = kernel32.GetFinalPathNameByHandleW(ctypes.c_void_p(msvcrt.get_osfhandle(fd)), buffer, len(buffer), 0)
        return buffer.value if 0 < length < len(buffer) else None
    except (OSError, ImportError, ValueError):
        return None

def _fd_reached_path(fd: int, path: str) -> bool:
    final = _handle_final_path(fd)
    return final is not None and final.casefold() == _expected_final(path)

def _close_and_remove_stray(fd: int, path: str) -> None:
    """Close fd; when the exclusive create landed behind a substituted parent, delete only that empty remnant."""
    try:
        final = _handle_final_path(fd)
        os.close(fd)
        if final is not None and final.casefold() != _expected_final(path):
            os.remove(final)
    except OSError:
        pass

def _derive_transport_root(local_appdata: str, nonce: str) -> str:
    return ntpath.join(local_appdata, *_TRANSPORT_SEGMENTS, nonce)

def _has_setup_assist_nonce(environment: Mapping[str, str]) -> bool:
    return _NONCE_ENV in environment

def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    if len({key for key, _ in pairs}) != len(pairs):
        raise ValueError("duplicate request key")
    return dict(pairs)

def _reject_constant(value: str) -> None:
    raise ValueError("non-finite request number")

def _validate_request(raw: bytes) -> tuple[tuple[tuple[str, bool], ...] | None, str | None]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, "request-undecodable"
    try:
        document = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except Exception:  # noqa: BLE001 - any parse defect fails closed
        return None, "request-malformed"
    if not isinstance(document, dict):
        return None, "request-malformed"
    if set(document) != {"schema", "operations"} or document["schema"] != _REQUEST_SCHEMA:
        return None, "schema-violation"
    operations = document["operations"]
    if not isinstance(operations, list) or not operations:
        return None, "schema-violation"
    if len(operations) > _MAX_OPERATIONS:
        return None, "too-many-operations"
    names: list[tuple[str, bool]] = []
    for item in operations:
        if not isinstance(item, dict):
            return None, "schema-violation"
        if any(_PATH_KEY.search(str(key)) for key in item):
            return None, "path-key-rejected"
        name = item.get("operation")
        if not isinstance(name, str):
            return None, "schema-violation"
        consent = item.get("consent", True)
        expected = {"operation", "consent"} if name == "env-block-apply" else {"operation"}
        if set(item) != expected or type(consent) is not bool:
            return None, "schema-violation"
        if name not in _ALLOWED_OPERATIONS:
            return None, "unknown-operation"
        if any(prior == name for prior, _ in names):
            return None, "duplicate-operation"
        names.append((name, consent))
    return tuple(names), None

def _read_request(path: str, fs: FsView) -> tuple[bytes | None, str | None]:
    kind = fs.file_kind(path)
    if kind != "file":
        return None, "request-missing" if kind == "missing" else "request-unsafe"
    try:
        handle = os.open(path, os.O_RDONLY | _O_BINARY)
        try:
            entry = os.fstat(handle)
            if entry.st_size > _MAX_FILE_BYTES:
                return None, "request-oversize"
            if not stat.S_ISREG(entry.st_mode) or getattr(entry, "st_file_attributes", 0) & _REPARSE:
                return None, "request-unsafe"
            if not _fd_reached_path(handle, path):  # parent swapped to a reparse point after validation
                return None, "request-unsafe"
            data = os.read(handle, _MAX_FILE_BYTES + 1)
        finally:
            os.close(handle)
    except OSError:
        return None, "request-unsafe"
    return (None, "request-oversize") if len(data) > _MAX_FILE_BYTES else (data, None)

def _write_result(root: str, payload: Mapping[str, object], fs: FsView) -> bool:
    path, data = ntpath.join(root, "result.json"), json.dumps(payload, sort_keys=True).encode("utf-8")
    if fs.file_kind(path) != "missing" or len(data) > _MAX_FILE_BYTES:
        return False
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_BINARY, 0o600)
    except OSError:
        return False
    if not _fd_reached_path(fd, path):  # O_EXCL guards the leaf only; the parent may have been substituted
        _close_and_remove_stray(fd, path)
        return False
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
    except OSError:
        return False
    return True

def _execute(names: tuple[tuple[str, bool], ...], environment: Mapping[str, str], local_appdata: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for name, consent in names:
        if name == "discover":
            report = discovery.discover(environment)
            records.append({"operation": name, "status": "ok", "facts": {"outcome": report.outcome, "config-home-state": report.config_home_state, "env-file-state": report.env_file_state or "unavailable", "process-status": report.process_status}})
        elif name == "yasb-running":
            records.append({"operation": name, "status": "ok", "facts": {"process-status": discovery.probe_running_yasb().status}})
        elif name == "env-block-apply":
            home = discovery.resolve_config_home(environment)
            invocation = discovery.resolve_installed_invocation(sys.executable)
            if not consent:
                records.append({"operation": name, "status": "refused", "reason": "env-consent-required"})
            elif home.path is None or home.state != discovery.HOME_RESOLVED:
                records.append({"operation": name, "status": "refused", "reason": "env-home-unsafe"})
            elif invocation.state != discovery.INVOCATION_RESOLVED or invocation.command is None:
                records.append({"operation": name, "status": "refused", "reason": "env-invocation-unavailable"})
            else:
                result = _env_block.apply(Path(home.path), Path(local_appdata) / "yasb-limitora", invocation.command, consent=True)
                records.append({"operation": name, "status": "ok"} if result.reason is None else {"operation": name, "status": "refused", "reason": result.reason})
        else:  # semantics arrive in S07-S09; a bounded nonfatal refusal keeps the program transaction continuable
            records.append({"operation": name, "status": "refused", "reason": "operation-unavailable"})
    return records

def _run_setup_assist(environment: Mapping[str, str], *, local_appdata: str | None = None,
                      fs: FsView = discovery.REAL_FS, appdata_resolver: Callable[[], str | None] = resolve_local_appdata) -> int:
    if not _valid_nonce(environment.get(_NONCE_ENV, "")):
        return 1  # nonce grammar is validated before any filesystem access
    resolved = local_appdata if local_appdata is not None else appdata_resolver()
    if not isinstance(resolved, str) or (canonical := _canonical_local_dir(resolved)) is None:
        return 1
    root = _derive_transport_root(canonical, str(environment[_NONCE_ENV]))
    if not _components_safe(root, fs):
        return 1  # unsafe or reparse transport component: refuse without writing
    if not fs.is_dir(root):
        return 1  # the assist never creates the nonce directory; setup.exe owns it
    data, defect = _read_request(ntpath.join(root, "request.json"), fs)
    names, violation = _validate_request(data or b"") if defect is None else (None, None)
    if defect is not None or violation is not None or names is None:
        reason = defect or violation or "request-malformed"
        refusal = {"schema": _RESULT_SCHEMA, "status": "refused", "operations": [{"operation": "request", "status": "refused", "reason": reason}]}
        _write_result(root, refusal, fs)
        return 1
    records = _execute(names, environment, canonical)
    status = "complete" if all(record["status"] == "ok" for record in records) else "partial"
    if not _write_result(root, {"schema": _RESULT_SCHEMA, "status": status, "operations": records}, fs):
        return 1
    return 0 if status == "complete" else 1
