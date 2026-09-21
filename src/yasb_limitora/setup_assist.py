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

import contextlib
import ctypes
import json
import ntpath
import os
import re
import stat
import sys
import tempfile
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from . import _config_lock, _env_block, _path_cleanup, config, discovery
from .discovery import FsView, _canonical_local_dir, _components_safe
from .path import MAX_CONFIG_BYTES

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
_CONFIG_SELECTION_FIELDS = {
    "deadline_seconds": frozenset(),
    "codex": frozenset({"enabled", "runner", "timeout_seconds"}),
    "opencode_go": frozenset({"enabled", "timeout_seconds"}),
}
_BACKUP_NAME = re.compile(r"config\\..+\\.json\\Z")
_GATE_ONE = object()

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

def _validate_request(raw: bytes) -> tuple[tuple[tuple[str, object], ...] | None, str | None]:
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
    names: list[tuple[str, object]] = []
    for item in operations:
        if not isinstance(item, dict):
            return None, "schema-violation"
        if any(_PATH_KEY.search(str(key)) for key in item):
            return None, "path-key-rejected"
        name = item.get("operation")
        if not isinstance(name, str):
            return None, "schema-violation"
        if name == "env-block-apply":
            if set(item) != {"operation", "consent"} or type(item.get("consent")) is not bool:
                return None, "schema-violation"
            consent: object = item["consent"]
        elif name == "state-cleanup":
            if set(item) != {"operation", "consent"} or item.get("consent") != "YES":
                return None, "schema-violation"
            consent = item["consent"]
        elif name == "config-apply":
            if set(item) != {"operation", "selection"} or not _valid_config_selection(item.get("selection")):
                return None, "schema-violation"
            consent = item["selection"]
        else:
            if set(item) != {"operation"}:
                return None, "schema-violation"
            consent = True
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

def _config_diagnostic(error: config.ConfigError) -> dict[str, str]:
    """Project a config failure without retaining fields or values from user data."""
    message = str(error)
    if "duplicate" in message:
        reason = "duplicate-key"
    elif "non-finite" in message:
        reason = "non-finite-number"
    elif "undecodable" in message:
        reason = "undecodable-input"
    elif "malformed" in message:
        reason = "malformed-json"
    elif "credential-like" in message:
        reason = "credential-like-key"
    elif "unsupported" in message:
        reason = "unknown-field"
    else:
        reason = "wrong-type"
    return {"field": "config", "reason": reason}


def _read_gate_one_config(path: Path) -> bytes:
    """Read only the verified handle for the literal existing config path."""
    if not _components_safe(str(path.parent), discovery.REAL_FS):
        raise OSError("unsafe config parent")
    fd = os.open(path, os.O_RDONLY | _O_BINARY | getattr(os, "O_NOFOLLOW", 0))
    try:
        entry = os.fstat(fd)
        if not stat.S_ISREG(entry.st_mode) or entry.st_size > MAX_CONFIG_BYTES or getattr(entry, "st_file_attributes", 0) & _REPARSE:
            raise OSError("unsafe config")
        if not _fd_reached_path(fd, str(path)):
            raise OSError("config path changed")
        data = os.read(fd, MAX_CONFIG_BYTES + 1)
        if len(data) > MAX_CONFIG_BYTES:
            raise OSError("oversize config")
        return data
    finally:
        os.close(fd)


def _config_parent_state(parent: str, fs: FsView = discovery.REAL_FS) -> str:
    if not _components_safe(parent, fs):
        return "unsafe"
    kind = fs.file_kind(parent)
    return "present" if kind == "dir" else "absent" if kind == "missing" else "unsafe"


def _snapshot_from_owned(path: str, lease: _config_lock.ConfigLease) -> config.ConfigSnapshot:
    if not lease.owned:
        raise OSError("config lease is not owned")
    try:
        raw = _read_gate_one_config(Path(path))
    except FileNotFoundError:
        if not os.path.lexists(path):
            return config.ConfigSnapshot(None, None, frozenset(), config.CONFIG_ABSENT)
        raise OSError("unsafe config") from None
    provider_errors: set[config.ProviderKey] = set()
    local = config.validate_config_document(raw, provider_errors)
    return config.ConfigSnapshot(raw, local, frozenset(provider_errors), config.CONFIG_PRESENT)


def _config_snapshot(local_appdata: str, *, lease_factory: Callable[..., Any] | None = None) -> config.ConfigSnapshot:
    path = _config_lock._fixed_config_path(local_appdata)
    state = _config_parent_state(ntpath.dirname(path))
    if state == "absent":
        return config.ConfigSnapshot(None, None, frozenset(), config.CONFIG_ABSENT)
    if state != "present":
        raise OSError("unsafe config parent")
    factory = _config_lock.config_lease if lease_factory is None else lease_factory
    with factory(local_appdata) as lease:
        return _snapshot_from_owned(path, lease)


def _valid_config_selection(selection: object) -> bool:
    if not isinstance(selection, Mapping) or not selection:
        return False
    for key, value in selection.items():
        allowed = _CONFIG_SELECTION_FIELDS.get(key)
        if allowed is None:
            return False
        if key == "deadline_seconds":
            continue
        if not isinstance(value, Mapping) or not value or any(field not in allowed for field in value):
            return False
    return True


def _ordered_config_document(raw: bytes) -> dict[str, object]:
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (UnicodeDecodeError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("invalid configuration document") from error
    if not isinstance(document, dict):
        raise TypeError("configuration document is not an object")
    return document


def _merge_config_selection(raw: bytes, selection: Mapping[str, object]) -> bytes:
    document = _ordered_config_document(raw)
    for key, value in selection.items():
        if key == "deadline_seconds":
            document[key] = value
            continue
        current = document.get(key)
        if current is None:
            current = {}
            document[key] = current
        if not isinstance(current, dict) or not isinstance(value, Mapping):
            raise TypeError("configuration selection has an invalid provider shape")
        for field, selected in value.items():
            current[field] = selected
    return json.dumps(document, ensure_ascii=True, allow_nan=False).encode("utf-8")


def _write_fsynced(path: Path, data: bytes, *, exclusive: bool = True) -> None:
    flags = os.O_WRONLY | os.O_CREAT | _O_BINARY
    if exclusive:
        flags |= os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            fd = -1
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if fd != -1:
            os.close(fd)


def _create_config_backup(path: Path, raw: bytes) -> Path:
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    if not backup_dir.is_dir():
        raise OSError("unsafe backup directory")
    stamp = time.time_ns()
    backup = backup_dir / f"config.{stamp}.json"
    while backup.exists():
        stamp += 1
        backup = backup_dir / f"config.{stamp}.json"
    _write_fsynced(backup, raw)
    return backup


def _prune_config_backups(directory: Path) -> None:
    backups = [
        entry for entry in directory.iterdir()
        if _BACKUP_NAME.fullmatch(entry.name) and entry.is_file() and not entry.is_symlink()
    ]
    backups.sort(key=lambda entry: (entry.stat().st_mtime_ns, entry.name))
    for entry in backups[:-5]:
        entry.unlink()


def _atomic_config_write(path: Path, data: bytes) -> None:
    temporary: str | None = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=".config.", suffix=".tmp", dir=str(path.parent))
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            with contextlib.suppress(OSError):
                os.unlink(temporary)


def _verify_config_reread(original: bytes, reread: bytes, merged: bytes, selection: Mapping[str, object]) -> None:
    original_document = _ordered_config_document(original)
    reread_document = _ordered_config_document(reread)
    for key, selected in selection.items():
        if key == "deadline_seconds":
            if reread_document.get(key, _GATE_ONE) != selected:
                raise OSError("selected configuration path changed")
            continue
        reread_provider = reread_document.get(key)
        if not isinstance(selected, Mapping) or not isinstance(reread_provider, dict):
            raise OSError("selected configuration path changed")
        for field, value in selected.items():
            if reread_provider.get(field, _GATE_ONE) != value:
                raise OSError("selected configuration path changed")

    def unowned(document: dict[str, object]) -> dict[str, object]:
        result = dict(document)
        for key, selected in selection.items():
            if key == "deadline_seconds":
                result.pop(key, None)
            else:
                provider_value = result.get(key)
                if not isinstance(selected, Mapping) or not isinstance(provider_value, dict):
                    continue
                provider = dict(provider_value)
                for field in selected:
                    provider.pop(field, None)
                if provider:
                    result[key] = provider
                else:
                    result.pop(key, None)
        return result

    if unowned(reread_document) != unowned(original_document) or reread != merged:
        raise OSError("configuration verification failed")


def _rollback_config_write(path: Path, backup: Path | None, lease: _config_lock.ConfigLease) -> None:
    if not lease.owned:
        raise OSError("config lease is not owned")
    if backup is None:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()
        if not lease.owned or os.path.lexists(path):
            raise OSError("config absence verification failed")
        return
    restored = backup.read_bytes()
    if not lease.owned:
        raise OSError("config lease is not owned")
    _atomic_config_write(path, restored)
    if not lease.owned or _read_gate_one_config(path) != restored:
        raise OSError("config restoration verification failed")


def _consume_config_snapshot(
    snapshot: config.ConfigSnapshot,
    lease: _config_lock.ConfigLease,
    selection: object = _GATE_ONE,
    path: str | None = None,
) -> dict[str, object]:
    if not lease.owned:
        raise OSError("config lease is not owned")
    if not snapshot.present and selection is _GATE_ONE:
        return {"operation": "config-apply", "status": "refused", "reason": "config-absent"}
    diagnostics = [{"provider": key.value, "reason": "provider-invalid"} for key in sorted(snapshot.provider_errors, key=lambda item: item.value)]
    result: dict[str, object] = {"operation": "config-apply", "status": "refused", "reason": "config-gate-2-unavailable"}
    if diagnostics:
        result["diagnostics"] = diagnostics
    if selection is _GATE_ONE:
        return result
    if not _valid_config_selection(selection) or path is None:
        return {"operation": "config-apply", "status": "refused", "reason": "config-selection-invalid"}
    if snapshot.provider_errors:
        return result
    selected = selection
    if not isinstance(selected, Mapping):
        return {"operation": "config-apply", "status": "refused", "reason": "config-selection-invalid"}
    try:
        merged = _merge_config_selection(snapshot.raw_bytes if snapshot.raw_bytes is not None else b"{}", selected)
        config.validate_config_document(merged)
    except (config.ConfigError, TypeError, ValueError, UnicodeError, OverflowError):
        return {"operation": "config-apply", "status": "refused", "reason": "config-selection-invalid"}
    if not lease.owned:
        raise OSError("config lease is not owned")
    config_path = Path(path)
    backup: Path | None = None
    replaced = False
    try:
        if snapshot.present:
            backup = _create_config_backup(config_path, snapshot.raw_bytes or b"")
        if not lease.owned:
            raise OSError("config lease is not owned")
        _atomic_config_write(config_path, merged)
        replaced = True
        if not lease.owned:
            raise OSError("config lease is not owned")
        reread = _read_gate_one_config(config_path)
        config.validate_config_document(reread)
        _verify_config_reread(snapshot.raw_bytes or b"{}", reread, merged, selected)
        if snapshot.present:
            _prune_config_backups(config_path.parent / "backups")
        return {"operation": "config-apply", "status": "ok"}
    except Exception:  # noqa: BLE001 - write path fails closed and attempts rollback
        if replaced:
            try:
                _rollback_config_write(config_path, backup, lease)
            except OSError:
                return {"operation": "config-apply", "status": "refused", "reason": "config-rollback-failed"}
        return {"operation": "config-apply", "status": "refused", "reason": "config-write-failed"}


def _config_gate_one(local_appdata: str, selection: object = _GATE_ONE) -> dict[str, object]:
    """Validate the existing config once while the fixed-path lease remains owned."""
    path = _config_lock._fixed_config_path(local_appdata)
    parent = ntpath.dirname(path)
    parent_state = _config_parent_state(parent)
    if parent_state == "absent":
        if selection is _GATE_ONE:
            return {"operation": "config-apply", "status": "refused", "reason": "config-absent"}
        if not _valid_config_selection(selection):
            return {"operation": "config-apply", "status": "refused", "reason": "config-selection-invalid"}
        try:
            Path(parent).mkdir(parents=True, exist_ok=True)
        except OSError:
            return {"operation": "config-apply", "status": "refused", "reason": "configuration-invalid", "diagnostics": [{"field": "config", "reason": "unreadable-input"}]}
        parent_state = _config_parent_state(parent)
    if parent_state != "present":
        return {"operation": "config-apply", "status": "refused", "reason": "configuration-invalid", "diagnostics": [{"field": "config", "reason": "unreadable-input"}]}
    try:
        with _config_lock.config_lease(local_appdata) as lease:
            try:
                snapshot = _snapshot_from_owned(path, lease)
            except config.ConfigError as error:
                return {"operation": "config-apply", "status": "refused", "reason": "configuration-invalid", "diagnostics": [_config_diagnostic(error)]}
            except OSError:
                return {"operation": "config-apply", "status": "refused", "reason": "configuration-invalid", "diagnostics": [{"field": "config", "reason": "unreadable-input"}]}
            if selection is _GATE_ONE:
                return _consume_config_snapshot(snapshot, lease)
            return _consume_config_snapshot(snapshot, lease, selection, path)
    except (_config_lock.GuardError, OSError):
        return {"operation": "config-apply", "status": "refused", "reason": "configuration-invalid", "diagnostics": [{"field": "config", "reason": "unreadable-input"}]}


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

def _execute(names: tuple[tuple[str, object], ...], environment: Mapping[str, str], local_appdata: str,
             registry: _path_cleanup.UserPathRegistry | None = None) -> list[dict[str, object]]:
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
        elif name in {"path-add", "path-remove"}:
            path_registry = registry or _path_cleanup.WindowsUserPathRegistry()
            result = _path_cleanup.append_user_path(path_registry, os.path.dirname(sys.executable)) if name == "path-add" else _path_cleanup.remove_recorded_user_path(path_registry)
            records.append({"operation": name, "status": "ok"} if result.changed else {"operation": name, "status": "refused", "reason": result.reason or "path-unchanged"})
        elif name == "state-cleanup":
            if consent != "YES":
                records.append({"operation": name, "status": "refused", "reason": "state-consent-required"})
            else:
                path_registry = registry or _path_cleanup.WindowsUserPathRegistry()
                state_dir = ntpath.join(local_appdata, "yasb-limitora")
                result = _path_cleanup.cleanup_literal_state(path_registry, state_dir)
                records.append({"operation": name, "status": "ok"} if result.changed else {"operation": name, "status": "refused", "reason": result.reason or "state-unchanged"})
        elif name == "config-apply":
            records.append(_config_gate_one(local_appdata) if isinstance(consent, bool) else _config_gate_one(local_appdata, consent))
        else:  # semantics arrive in S09+; a bounded nonfatal refusal keeps the program transaction continuable
            records.append({"operation": name, "status": "refused", "reason": "operation-unavailable"})
    return records

def _run_setup_assist(environment: Mapping[str, str], *, local_appdata: str | None = None,
                      fs: FsView = discovery.REAL_FS, appdata_resolver: Callable[[], str | None] = resolve_local_appdata,
                      registry: _path_cleanup.UserPathRegistry | None = None) -> int:
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
    records = _execute(names, environment, canonical, registry)
    status = "complete" if all(record["status"] == "ok" for record in records) else "partial"
    if not _write_result(root, {"schema": _RESULT_SCHEMA, "status": status, "operations": records}, fs):
        return 1
    return 0 if status == "complete" else 1
