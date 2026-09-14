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
from typing import Any

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
