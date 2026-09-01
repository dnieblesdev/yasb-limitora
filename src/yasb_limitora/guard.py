"""Opaque, bounded Win32 mutex acquisition for the JSON contract."""

from __future__ import annotations

from dataclasses import dataclass
import ctypes
import hashlib
import os
from collections.abc import Callable

from .deadline import DeadlineContext
from .path import canonicalize_path


WAIT_OBJECT_0 = 0x00000000
WAIT_ABANDONED = 0x00000080
WAIT_TIMEOUT = 0x00000102
WAIT_FAILED = 0xFFFFFFFF
MAX_WAIT_NS = 250_000_000


class _SecurityAttributes(ctypes.Structure):
    _fields_ = (
        ("nLength", ctypes.c_uint32),
        ("lpSecurityDescriptor", ctypes.c_void_p),
        ("bInheritHandle", ctypes.c_int),
    )


class _TokenUser(ctypes.Structure):
    _fields_ = (("Sid", ctypes.c_void_p), ("Attributes", ctypes.c_uint32))


class GuardError(RuntimeError):
    """A sanitized guard acquisition or cleanup error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _valid_sid_bytes(value: object) -> bool:
    return (
        isinstance(value, bytes)
        and 8 <= len(value) <= 68
        and value[0] == 1
        and len(value) == 8 + 4 * value[1]
    )


class _NativeWin32:
    def __init__(self) -> None:
        if os.name != "nt":
            raise GuardError("guard_acquisition_failed")
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        self._kernel32.CreateMutexW.argtypes = [ctypes.POINTER(_SecurityAttributes), ctypes.c_int, ctypes.c_wchar_p]
        self._kernel32.CreateMutexW.restype = ctypes.c_void_p
        self._kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self._kernel32.WaitForSingleObject.restype = ctypes.c_uint32
        self._kernel32.ReleaseMutex.argtypes = [ctypes.c_void_p]
        self._kernel32.ReleaseMutex.restype = ctypes.c_int
        self._kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        self._kernel32.CloseHandle.restype = ctypes.c_int

    def CreateMutexW(self, _security_attributes, initial_owner: bool, name: str):
        descriptor = ctypes.c_void_p()
        convert = self._advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW
        convert.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
        convert.restype = ctypes.c_int
        if not convert("D:(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;OW)", 1, ctypes.byref(descriptor), None):
            raise GuardError("guard_acquisition_failed")
        attributes = _SecurityAttributes(ctypes.sizeof(_SecurityAttributes), descriptor, 0)
        try:
            return self._kernel32.CreateMutexW(ctypes.byref(attributes), bool(initial_owner), name)
        finally:
            self._kernel32.LocalFree(descriptor)

    def WaitForSingleObject(self, handle, timeout_ms: int) -> int:
        return int(self._kernel32.WaitForSingleObject(handle, timeout_ms))

    def ReleaseMutex(self, handle) -> bool:
        return bool(self._kernel32.ReleaseMutex(handle))

    def CloseHandle(self, handle) -> bool:
        return bool(self._kernel32.CloseHandle(handle))


def _default_sid_bytes() -> bytes:
    if os.name != "nt":
        raise GuardError("guard_acquisition_failed")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    token = ctypes.c_void_p()
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    open_token = advapi32.OpenProcessToken
    open_token.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
    open_token.restype = ctypes.c_int
    if not open_token(kernel32.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
        raise GuardError("guard_acquisition_failed")
    try:
        get_information = advapi32.GetTokenInformation
        get_information.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
        get_information.restype = ctypes.c_int
        required = ctypes.c_uint32()
        get_information(token, 1, None, 0, ctypes.byref(required))
        if not required.value:
            raise GuardError("guard_acquisition_failed")
        buffer = ctypes.create_string_buffer(required.value)
        if not get_information(token, 1, buffer, required.value, ctypes.byref(required)):
            raise GuardError("guard_acquisition_failed")
        user = ctypes.cast(buffer, ctypes.POINTER(_TokenUser)).contents
        get_length = advapi32.GetLengthSid
        get_length.argtypes = [ctypes.c_void_p]
        get_length.restype = ctypes.c_uint32
        length = get_length(user.Sid)
        if not length:
            raise GuardError("guard_acquisition_failed")
        value = ctypes.string_at(user.Sid, length)
        if not _valid_sid_bytes(value):
            raise GuardError("guard_acquisition_failed")
        return value
    finally:
        kernel32.CloseHandle(token)


def _digest(hash_fn: Callable[[bytes], object], payload: bytes) -> str:
    result = hash_fn(payload)
    if hasattr(result, "hexdigest"):
        return str(result.hexdigest())
    if isinstance(result, bytes):
        return result.hex()
    raise GuardError("guard_acquisition_failed")


@dataclass(slots=True)
class GuardLease:
    api: object
    handle: object
    name: str
    owned: bool = True
    closed: bool = False

    def release(self) -> bool:
        if not self.owned:
            return True
        if self.closed:
            return False
        try:
            result = bool(self.api.ReleaseMutex(self.handle))
        except Exception:
            result = False
        if result:
            self.owned = False
        return result

    def close(self) -> bool:
        if self.closed:
            return True
        # Never close a handle while this lease still records mutex ownership.
        # A failed release remains retryable on the same native handle.
        if self.owned:
            return False
        try:
            result = bool(self.api.CloseHandle(self.handle))
        except Exception:
            return False
        if result:
            self.closed = True
        return result


class Guard:
    """Acquire one opaque named mutex for a SID/path tuple.

    The ``Global\\`` namespace is intentional: cross-session serialization for
    the same Windows user requires the runner to possess
    ``SeCreateGlobalPrivilege``. The native proof verifies acquisition in the
    privileged CI environment; the namespace is not changed to ``Local\\``.
    """

    def __init__(
        self,
        *,
        api: object | None = None,
        sid_provider: Callable[[], bytes] = _default_sid_bytes,
        hash_fn: Callable[[bytes], object] = hashlib.sha256,
        name_prefix: str = r"Global\yasb-limitora-v2-guard-",
    ) -> None:
        self._api = _NativeWin32() if api is None else api
        self._sid_provider = sid_provider
        self._hash_fn = hash_fn
        self._name_prefix = name_prefix

    def name_for(self, path: object) -> str:
        try:
            sid = self._sid_provider()
            if not _valid_sid_bytes(sid):
                raise ValueError
            canonical = canonicalize_path(path).casefold()
            payload = sid + b"\0" + canonical.encode("utf-8")
            return self._name_prefix + _digest(self._hash_fn, payload)
        except GuardError:
            raise
        except Exception:
            raise GuardError("guard_acquisition_failed") from None

    def acquire_key(self, key: bytes, context: DeadlineContext) -> GuardLease:
        """Acquire a mutex for an opaque non-path identity."""
        try:
            if not isinstance(key, bytes) or not key:
                raise GuardError("guard_acquisition_failed")
            sid = self._sid_provider()
            if not _valid_sid_bytes(sid):
                raise GuardError("guard_acquisition_failed")
            name = self._name_prefix + _digest(self._hash_fn, sid + b"\0" + key)
            return self._acquire_name(name, context)
        except GuardError:
            raise
        except Exception:
            raise GuardError("guard_acquisition_failed") from None

    def acquire(self, path: object, context: DeadlineContext) -> GuardLease:
        try:
            return self._acquire_name(self.name_for(path), context)
        except GuardError:
            raise
        except Exception:
            raise GuardError("guard_acquisition_failed") from None

    def _acquire_name(self, name: str, context: DeadlineContext) -> GuardLease:
        handle = None
        try:
            handle = self._api.CreateMutexW(None, False, name)
            if not handle:
                raise GuardError("guard_acquisition_failed")
            remaining_ns = context.remaining_ns()
            wait_ns = min(MAX_WAIT_NS, max(0, remaining_ns - context.reserve_ns))
            timeout_ms = min(MAX_WAIT_NS // 1_000_000, wait_ns // 1_000_000)
            result = self._api.WaitForSingleObject(handle, timeout_ms)
            if result in (WAIT_OBJECT_0, WAIT_ABANDONED):
                return GuardLease(self._api, handle, name)
            self._safe_close(handle)
            handle = None
            if result == WAIT_TIMEOUT:
                raise GuardError("guard_wait_timeout")
            raise GuardError("guard_acquisition_failed")
        except GuardError:
            raise
        except Exception:
            if handle:
                self._safe_close(handle)
            raise GuardError("guard_acquisition_failed") from None

    def _safe_close(self, handle: object) -> None:
        try:
            self._api.CloseHandle(handle)
        except Exception:
            pass


__all__ = (
    "GuardError",
    "GuardLease",
    "MAX_WAIT_NS",
    "Guard",
    "WAIT_ABANDONED",
    "WAIT_FAILED",
    "WAIT_OBJECT_0",
    "WAIT_TIMEOUT",
)
