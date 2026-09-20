"""D01a1/a2a/D01a2b — Guard domain, marker codec, and Win32 process identity.

Context-managed Guard lease keyed by the exact fixed config.json path,
retrying under one 5-second DeadlineContext; bounded release/close cleanup.
Canonical UTF-8 JSON marker with sorted keys, no whitespace, and strict
schema validation (D01a2a).  Win32 process-identity token via
OpenProcess/GetProcessTimes/CloseHandle with fail-closed semantics (D01a2b).
"""
from __future__ import annotations

import contextlib
import ctypes
import json
import ntpath
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, NamedTuple

from ._native_state_cleanup import _INFO
from .deadline import DeadlineContext
from .guard import Guard, GuardError, GuardLease

_CONFIG_DEADLINE_SECONDS = 5.0
_RELEASE_RETRIES = 3

_MARKER_KEYS = frozenset({"pid", "token", "version"})
_MARKER_VERSION = 1
_MARKER_MAX_BYTES = 256
_TOKEN_MAX_HEX = 64
_MARKER_ERROR = "marker-validation"


def _fixed_config_path(local_appdata: str) -> str:
    if not local_appdata or not local_appdata.strip():
        raise ValueError("blank LOCALAPPDATA")
    return ntpath.join(local_appdata, "yasb-limitora", "config.json")


@contextmanager
def config_lease(
    local_appdata: str,
    *,
    guard: Guard | None = None,
    deadline_seconds: float = _CONFIG_DEADLINE_SECONDS,
    clock_ns: Callable[[], int] | None = None,
) -> Iterator[GuardLease]:
    """Acquire and guarantee a Guard lease for the fixed config.json path."""
    config_path = _fixed_config_path(local_appdata)
    g = guard if guard is not None else Guard()
    ctx_kwargs: dict[str, Any] = {}
    if clock_ns is not None:
        ctx_kwargs["clock_ns"] = clock_ns
    ctx = DeadlineContext.from_seconds(deadline_seconds, **ctx_kwargs)
    lease: GuardLease | None = None
    try:
        while True:
            try:
                lease = g.acquire(config_path, ctx)
                break
            except GuardError as exc:
                if exc.code == "guard_wait_timeout":
                    if ctx.usable_ns() <= 0:
                        raise GuardError("config-lock-busy") from None
                    continue
                raise
        yield lease
    finally:
        if lease is not None:
            released = any(lease.release() for _ in range(_RELEASE_RETRIES))
            if not released:
                lease.owned = False
            closed = any(lease.close() for _ in range(_RELEASE_RETRIES))
            if not released:
                raise GuardError("config-lock-release-failed")
            if not closed:
                raise GuardError("config-lock-close-failed")


class MarkerValidationError(ValueError):
    """Marker failed validation — one stable public code, no cause leakage."""

    def __init__(self) -> None:
        super().__init__(_MARKER_ERROR)


def encode_marker(pid: int, token: str) -> bytes:
    """Encode canonical UTF-8 JSON marker (sorted keys, no whitespace)."""
    if not isinstance(pid, int) or isinstance(pid, bool) or not 1 <= pid <= 4294967295:
        raise MarkerValidationError()
    if not isinstance(token, str) or not token or len(token) > _TOKEN_MAX_HEX:
        raise MarkerValidationError()
    if not all(c in "0123456789abcdef" for c in token):
        raise MarkerValidationError()
    return json.dumps(
        {"pid": pid, "token": token, "version": _MARKER_VERSION},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def decode_marker(data: bytes) -> tuple[int, str, int]:
    """Decode canonical marker, rejecting invalid and noncanonical inputs."""
    if not data or len(data) > _MARKER_MAX_BYTES:
        raise MarkerValidationError()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise MarkerValidationError() from None
    # Reject noncanonical whitespace before parsing
    if any(c in text for c in " \t\n\r"):
        raise MarkerValidationError()

    def _check_dup_and_order(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        keys = [k for k, _ in pairs]
        if len(keys) != len(set(keys)):
            raise MarkerValidationError()
        if keys != sorted(keys):
            raise MarkerValidationError()
        return dict(pairs)

    try:
        obj = json.loads(text, object_pairs_hook=_check_dup_and_order)
    except json.JSONDecodeError:
        raise MarkerValidationError() from None
    if not isinstance(obj, dict):
        raise MarkerValidationError()
    if set(obj.keys()) != _MARKER_KEYS:
        raise MarkerValidationError()
    pid, token, version = obj["pid"], obj["token"], obj["version"]
    if not isinstance(pid, int) or isinstance(pid, bool) or not 1 <= pid <= 4294967295:
        raise MarkerValidationError()
    if not isinstance(token, str) or not token or len(token) > _TOKEN_MAX_HEX:
        raise MarkerValidationError()
    if not all(c in "0123456789abcdef" for c in token):
        raise MarkerValidationError()
    if not isinstance(version, int) or isinstance(version, bool) or version != _MARKER_VERSION:
        raise MarkerValidationError()
    # Roundtrip check: reject escaped/noncanonical byte spellings
    if data != encode_marker(pid, token):
        raise MarkerValidationError()
    return pid, token, version


# ── D01a2b — Win32 process identity ──────────────────────────────────
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class ProcessTokenMissing(ValueError):
    """OpenProcess error 87 — the only valid 'process not found' refusal."""

    def __init__(self) -> None:
        super().__init__("process-token-missing")


class ProcessTokenUnprovable(RuntimeError):
    """OpenProcess succeeded but query/close failed — token unprovable."""

    def __init__(self) -> None:
        super().__init__("process-token-unprovable")


def _default_win32_api() -> Any:
    """Return the real kernel32 API wrapper or None on non-Windows."""
    if os.name != "nt":
        return None

    class _Kernel32Api:
        def __init__(self) -> None:
            self._k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self._k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
            self._k32.OpenProcess.restype = ctypes.c_void_p
            _ft = ctypes.POINTER(_Filetime)
            self._k32.GetProcessTimes.argtypes = [ctypes.c_void_p, _ft, _ft, _ft, _ft]
            self._k32.GetProcessTimes.restype = ctypes.c_int
            self._k32.CloseHandle.argtypes = [ctypes.c_void_p]
            self._k32.CloseHandle.restype = ctypes.c_int

        def OpenProcess(self, access: int, inherit: int, pid: int) -> int:
            return self._k32.OpenProcess(access, inherit, pid) or 0

        def GetProcessTimes(self, handle: int) -> int | None:
            creation = _Filetime()
            exit_ft = _Filetime()
            kernel_ft = _Filetime()
            user_ft = _Filetime()
            if not self._k32.GetProcessTimes(handle, creation, exit_ft, kernel_ft, user_ft):
                return None
            return (creation.dwHighDateTime << 32) | creation.dwLowDateTime

        def CloseHandle(self, handle: int) -> bool:
            return bool(self._k32.CloseHandle(handle))

        def get_last_error(self) -> int:
            return ctypes.get_last_error()

    return _Kernel32Api()


class _Filetime(ctypes.Structure):
    _fields_ = (("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32))


def creation_token(pid: object, *, api: Any = None) -> str:
    """Return unpadded lowercase hex FILETIME creation token for *pid*.

    Raises ProcessTokenMissing only for OpenProcess error 87.
    Raises ProcessTokenUnprovable for all other failures.
    """
    if not isinstance(pid, int) or isinstance(pid, bool) or not 1 <= pid <= 4294967295:
        raise ProcessTokenUnprovable()
    if api is None:
        api = _default_win32_api()
    if api is None:
        raise ProcessTokenUnprovable()
    for n in ("OpenProcess", "GetProcessTimes", "CloseHandle"):
        if not callable(getattr(api, n, None)):
            raise ProcessTokenUnprovable()
    try:
        handle = api.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
    except Exception:  # noqa: BLE001
        raise ProcessTokenUnprovable() from None
    if not handle:
        try:
            err = api.get_last_error()
        except Exception:  # noqa: BLE001
            raise ProcessTokenUnprovable() from None
        raise ProcessTokenMissing() if err == 87 else ProcessTokenUnprovable()
    creation: int | None = None
    failed = False
    closed = False
    try:
        try:
            r = api.GetProcessTimes(handle)
        except Exception:  # noqa: BLE001
            failed = True
        else:
            if isinstance(r, int) and not isinstance(r, bool) and r >= 0:
                creation = r
            else:
                failed = True
    finally:
        with contextlib.suppress(Exception):
            closed = bool(api.CloseHandle(handle))
    if failed or creation is None or not closed:
        raise ProcessTokenUnprovable()
    return f"{creation:x}"


# ── D01a3a1 — Safe marker create and identity ────────────────────────
_MARKER_FILE = "yasb-limitora.lock"
_DEL, _GR, _GW = 0x10000, 0x80000000, 0x40000000
_RA, _WA = 0x80, 0x100
_CNEW, _OEXIST, _ANORM = 1, 3, 0x80
_FREPARSE, _FBACKUP = 0x200000, 0x2000000
_AREPARSE, _ADIR = 0x400, 0x10


class MarkerPrimitiveError(OSError):
    """Sanitized low-level marker failure — one stable code, no cause leakage."""

    def __init__(self, code: str = "marker-primitive") -> None:
        super().__init__(code)


class _FileDispositionInfo(ctypes.Structure):
    """FILE_DISPOSITION_INFO: 1-byte BOOLEAN per Win32 ABI."""
    _fields_ = [("DeleteFile", ctypes.c_byte)]


def _real_api() -> Any:
    """Return real kernel32 marker API or None off-Windows."""
    if os.name != "nt":
        return None
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    H, PI = ctypes.c_void_p, ctypes.POINTER(_INFO)
    k.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, H]
    k.CreateFileW.restype = H
    k.GetFileInformationByHandle.argtypes = [H, PI]
    k.GetFileInformationByHandle.restype = ctypes.c_int
    k.GetFinalPathNameByHandleW.argtypes = [H, ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32]
    k.GetFinalPathNameByHandleW.restype = ctypes.c_uint32
    k.CloseHandle.argtypes = [H]
    k.CloseHandle.restype = ctypes.c_int
    k.ReadFile.argtypes = [H, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), H]
    k.ReadFile.restype = ctypes.c_int
    k.WriteFile.argtypes = [H, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), H]
    k.WriteFile.restype = ctypes.c_int
    k.SetFilePointerEx.argtypes = [H, ctypes.c_longlong, ctypes.POINTER(ctypes.c_longlong), ctypes.c_uint32]
    k.SetFilePointerEx.restype = ctypes.c_int
    k.FlushFileBuffers.argtypes = [H]
    k.FlushFileBuffers.restype = ctypes.c_int
    k.SetFileInformationByHandle.argtypes = [H, ctypes.c_int, ctypes.POINTER(_FileDispositionInfo), ctypes.c_uint32]
    k.SetFileInformationByHandle.restype = ctypes.c_int

    class _Api:
        def create_file(self, path, access, share, disp, attrs):
            return k.CreateFileW(path, access, share, None, disp, attrs, None) or 0

        def query_info(self, handle):
            info = _INFO()
            if not k.GetFileInformationByHandle(handle, ctypes.byref(info)):
                return None
            return info.Attributes, info.Volume, info.IndexHigh, info.IndexLow

        def final_path(self, handle):
            n = k.GetFinalPathNameByHandleW(handle, None, 0, 0)
            if not n:
                return None
            buf = ctypes.create_unicode_buffer(n + 1)
            if not k.GetFinalPathNameByHandleW(handle, buf, len(buf), 0):
                return None
            return os.path.normcase(buf.value.removeprefix("\\\\?\\"))

        def close(self, handle):
            return bool(k.CloseHandle(handle))

        def read_file(self, handle, max_bytes):
            buf = ctypes.create_string_buffer(max_bytes + 1)
            n = ctypes.c_uint32()
            if not k.ReadFile(handle, buf, max_bytes + 1, ctypes.byref(n), None):
                return None
            return buf.raw[: n.value]

        def write_file(self, handle, data):
            n = ctypes.c_uint32()
            if not k.WriteFile(handle, data, len(data), ctypes.byref(n), None):
                return 0
            return n.value

        def set_file_pointer(self, handle, offset, origin=0):
            prev = ctypes.c_longlong()
            if not k.SetFilePointerEx(handle, ctypes.c_longlong(offset), ctypes.byref(prev), origin):
                return None
            return prev.value

        def flush(self, handle):
            return bool(k.FlushFileBuffers(handle))

        def set_disposition(self, handle):
            delete = _FileDispositionInfo()
            delete.DeleteFile = 1
            return bool(k.SetFileInformationByHandle(handle, 4, ctypes.byref(delete), ctypes.sizeof(delete)))

    return _Api()


def safe_close(handle: int, api: Any) -> None:
    """Close handle, suppressing all errors."""
    with contextlib.suppress(Exception):
        api.close(handle)


class ParentHold(NamedTuple):
    path: str
    handle: int
    identity: tuple[int, int, int]


class ProbeWitness:
    """Opaque proof of successful identity verification, bound to the original handle."""

    __slots__ = ("_handle", "_identity")

    def __init__(self, handle: int, identity: tuple[int, int, int]) -> None:
        if not isinstance(handle, int) or isinstance(handle, bool) or handle <= 0:
            raise MarkerPrimitiveError()
        self._handle = handle
        self._identity = identity


def verify_parent(path: str, *, api: Any) -> ParentHold:
    """Verify and retain a parent handle that denies delete sharing."""
    h = api.create_file(path, _GR | _RA, 3, _OEXIST, _FREPARSE | _FBACKUP)
    if not h or h == -1:
        raise MarkerPrimitiveError()
    try:
        q = api.query_info(h)
        if q is None:
            raise MarkerPrimitiveError()
        attr, vol, ih, il = q
        fp = api.final_path(h)
        expected = os.path.normcase(os.path.abspath(path))
        if attr & _AREPARSE or not (attr & _ADIR) or fp != expected:
            raise MarkerPrimitiveError()
        return ParentHold(fp, h, (vol, ih, il))
    except MarkerPrimitiveError:
        safe_close(h, api)
        raise
    except Exception:  # noqa: BLE001
        safe_close(h, api)
        raise MarkerPrimitiveError() from None


def create_exclusive(parent: ParentHold, *, api: Any) -> tuple[int, str, tuple[int, int, int]]:
    """CREATE_NEW for fixed marker leaf; compare final_path to expected canonical."""
    for n in ("create_file", "query_info", "final_path", "close"):
        if not callable(getattr(api, n, None)):
            raise MarkerPrimitiveError()
    mp = ntpath.join(parent.path, _MARKER_FILE)
    access = _DEL | _GR | _GW | _RA | _WA
    h = api.create_file(mp, access, 7, _CNEW, _ANORM)
    if not h or h == -1:
        raise MarkerPrimitiveError()
    try:
        q = api.query_info(h)
        if q is None:
            raise MarkerPrimitiveError()
        attr, vol, ih, il = q
        if attr & _AREPARSE or (attr & _ADIR):
            raise MarkerPrimitiveError()
        fp = api.final_path(h)
        if fp is None:
            raise MarkerPrimitiveError()
        if fp != os.path.normcase(os.path.abspath(mp)):
            raise MarkerPrimitiveError()
        return h, fp, (vol, ih, il)
    except MarkerPrimitiveError:
        safe_close(h, api)
        raise
    except Exception:  # noqa: BLE001
        safe_close(h, api)
        raise MarkerPrimitiveError() from None


# ── D01a3a2a — Durable marker IO ─────────────────────────────────────



def read_marker(handle: int, *, api: Any) -> bytes:
    if not callable(getattr(api, "read_file", None)):
        raise MarkerPrimitiveError()
    if not callable(getattr(api, "set_file_pointer", None)):
        raise MarkerPrimitiveError()
    if api.set_file_pointer(handle, 0, 0) is None:
        raise MarkerPrimitiveError()
    data = api.read_file(handle, _MARKER_MAX_BYTES)
    if data is None or len(data) > _MARKER_MAX_BYTES:
        raise MarkerPrimitiveError()
    return data


def write_marker(handle: int, data: bytes, *, api: Any) -> bool:
    if not isinstance(data, bytes) or not data or len(data) > _MARKER_MAX_BYTES:
        raise MarkerPrimitiveError()
    if not callable(getattr(api, "write_file", None)):
        raise MarkerPrimitiveError()
    if not callable(getattr(api, "flush", None)):
        raise MarkerPrimitiveError()
    remaining, offset = len(data), 0
    while remaining > 0:
        n = api.write_file(handle, data[offset:])
        if not isinstance(n, int) or isinstance(n, bool) or n <= 0 or n > remaining:
            raise MarkerPrimitiveError()
        offset += n
        remaining -= n
    if not api.flush(handle):
        raise MarkerPrimitiveError()
    return True


# ── D01a3a2b — Identity re-open and disposition delete ───────────────


def identity_reopen(
    path: str,
    *,
    parent: ParentHold,
    expected: tuple[int, int, int],
    original: int,
    api: Any,
) -> ProbeWitness:
    """OPEN_EXISTING probe; verify path, attrs, identity; always close probe; return witness."""
    for n in ("create_file", "query_info", "final_path", "close"):
        if not callable(getattr(api, n, None)):
            raise MarkerPrimitiveError()
    h = api.create_file(path, _DEL | _GR | _RA, 7, _OEXIST, _ANORM)
    if not h or h == -1:
        raise MarkerPrimitiveError()
    verified: tuple[int, int, int] | None = None
    close_ok = False
    try:
        q = api.query_info(h)
        if q is None:
            raise MarkerPrimitiveError()
        attr, vol, ih, il = q
        if attr & _AREPARSE or (attr & _ADIR):
            raise MarkerPrimitiveError()
        fp = api.final_path(h)
        if fp is None:
            raise MarkerPrimitiveError()
        leaf = os.path.normcase(os.path.abspath(ntpath.join(parent.path, _MARKER_FILE)))
        if fp != leaf:
            raise MarkerPrimitiveError()
        if (vol, ih, il) != expected:
            raise MarkerPrimitiveError()
        verified = (vol, ih, il)
    except MarkerPrimitiveError:
        raise
    except Exception:  # noqa: BLE001
        raise MarkerPrimitiveError() from None
    finally:
        try:
            close_ok = bool(api.close(h))
        except Exception:  # noqa: BLE001
            close_ok = False
    if verified is None or not close_ok:
        raise MarkerPrimitiveError()
    return ProbeWitness(original, verified)


def disposition_delete(handle: int, *, witness: ProbeWitness, api: Any) -> bool:
    """SetFileInformationByHandle(FileDispositionInfo) — requires witness proof."""
    if not isinstance(witness, ProbeWitness) or handle != witness._handle:
        raise MarkerPrimitiveError()
    for n in ("query_info", "set_disposition"):
        if not callable(getattr(api, n, None)):
            raise MarkerPrimitiveError()
    try:
        q = api.query_info(handle)
        if q is None:
            raise MarkerPrimitiveError()
        if q[1:] != witness._identity:
            raise MarkerPrimitiveError()
        if not api.set_disposition(handle):
            raise MarkerPrimitiveError()
    except MarkerPrimitiveError:
        raise
    except Exception:  # noqa: BLE001
        raise MarkerPrimitiveError() from None
    return True
