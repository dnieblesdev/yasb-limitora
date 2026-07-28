"""Private Codex helper bootstrap/readiness contract."""

import math as _math
import os as _os
import secrets as _secrets
import subprocess as _subprocess
import threading as _threading
import time as _time
from dataclasses import dataclass as _dataclass
import typing as _typing

from ._codex_resource_core import (
    _CloseOutcome,
    _FdIdentity,
    _GenerationRegistry,
    _GenerationToken,
    _IndeterminateCleanupError,
    _IpcPair,
    _OwnerToken,
    _OwnedEndpoint,
    _StaleGenerationError,
    _new_endpoint_spec,
    _new_ipc_pair,
)

__all__: tuple[str, ...] = ()

_CONTROL_CAPACITY = 4096
_DEFAULT_TRANSPORT_TIMEOUT = 2.0
_TRANSPORT_BACKOFF = 0.001
_ERROR_BROKEN_PIPE = 109
_SPAWN_LOCK = _threading.RLock()


class _TransportError(RuntimeError):
    """Private bounded-control transport failure."""


class _TransportTimeout(_TransportError):
    """Private bounded-control transport timeout."""


def _peek_named_pipe(fd: int) -> tuple[int, bool]:
    """Return available bytes and EOF state for a native named pipe."""
    try:
        import ctypes
        import msvcrt

        available = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.PeekNamedPipe(
            msvcrt.get_osfhandle(fd), None, 0, None, ctypes.byref(available), None
        )
        if ok:
            return int(available.value), False
        if ctypes.windll.kernel32.GetLastError() == _ERROR_BROKEN_PIPE:
            return 0, True
    except Exception:
        pass
    raise _TransportError("peek_failed") from None


class _PipeTransport:
    """Bounded byte transport for the private gate/data control frames."""

    def __init__(
        self,
        read_fd: int,
        write_fd: int,
        *,
        peek: _typing.Callable[[int], tuple[int, bool]] = _peek_named_pipe,
        read: _typing.Callable[[int, int], bytes] = _os.read,
        write: _typing.Callable[[int, bytes], int] = _os.write,
        clock: _typing.Callable[[], float] = _time.monotonic,
        sleep: _typing.Callable[[float], None] = _time.sleep,
        nonblocking: bool = False,
    ) -> None:
        if not nonblocking:
            raise _TransportError("nonblocking_required")
        self._read_fd = read_fd
        self._write_fd = write_fd
        self._peek = peek
        self._read = read
        self._write = write
        self._clock = clock
        self._sleep = sleep

    def _deadline(self, timeout_seconds: object) -> float:
        if type(timeout_seconds) not in (int, float):
            raise _TransportTimeout("invalid_timeout") from None
        try:
            timeout = float(timeout_seconds)
        except (ValueError, OverflowError):
            raise _TransportTimeout("invalid_timeout") from None
        if timeout < 0 or not _math.isfinite(timeout):
            raise _TransportTimeout("invalid_timeout") from None
        return self._clock() + timeout

    def _backoff(self, deadline: float) -> None:
        remaining = deadline - self._clock()
        if remaining <= 0:
            raise _TransportTimeout("timeout") from None
        self._sleep(min(_TRANSPORT_BACKOFF, remaining))

    def read_frame(
        self,
        *,
        expected_size: int,
        timeout_seconds: object = _DEFAULT_TRANSPORT_TIMEOUT,
        max_size: int = _CONTROL_CAPACITY,
    ) -> bytes:
        if type(expected_size) is not int or not 0 < expected_size <= max_size:
            raise _TransportError("invalid_frame_size") from None
        deadline = self._deadline(timeout_seconds)
        result = bytearray()
        while len(result) < expected_size:
            available, eof = self._peek(self._read_fd)
            if eof:
                raise _TransportError("eof") from None
            remaining = expected_size - len(result)
            if available < 0 or available > max_size - len(result):
                raise _TransportError("frame_oversize") from None
            if available > remaining:
                raise _TransportError("trailing_data") from None
            if not available:
                self._backoff(deadline)
                continue
            try:
                chunk = self._read(self._read_fd, min(available, remaining))
            except BlockingIOError:
                self._backoff(deadline)
                continue
            except Exception:
                raise _TransportError("read_failed") from None
            if not chunk or len(chunk) > remaining:
                raise _TransportError("partial_read") from None
            result.extend(chunk)
        while True:
            available, eof = self._peek(self._read_fd)
            if available:
                raise _TransportError("trailing_data") from None
            if eof:
                return bytes(result)
            self._backoff(deadline)

    def write_control(
        self,
        data: bytes,
        *,
        timeout_seconds: object = _DEFAULT_TRANSPORT_TIMEOUT,
        capacity: int = _CONTROL_CAPACITY,
    ) -> None:
        if len(data) > capacity:
            raise _TransportError("frame_oversize") from None
        deadline = self._deadline(timeout_seconds)
        offset = 0
        while offset < len(data):
            try:
                written = self._write(self._write_fd, data[offset:])
            except BlockingIOError:
                self._backoff(deadline)
                continue
            except Exception:
                raise _TransportError("write_failed") from None
            if type(written) is not int or written < 0 or written > len(data) - offset:
                raise _TransportError("partial_write") from None
            if written == 0:
                self._backoff(deadline)
                continue
            offset += written

_GATE_ENV = "_YASB_CODEX_GATE_HANDLE"
_DATA_ENV = "_YASB_CODEX_DATA_HANDLE"
_NONCE_ENV = "_YASB_CODEX_READY_NONCE"
_NONCE_LIMIT = 128
_BOOTSTRAP = "\n".join(
    (
        "import os,msvcrt",
        "try:",
        f"    gate=msvcrt.open_osfhandle(int(os.environ.pop({_GATE_ENV!r})),0)",
        f"    data=msvcrt.open_osfhandle(int(os.environ.pop({_DATA_ENV!r})),1)",
        f"    nonce=os.environ.pop({_NONCE_ENV!r}).encode('ascii')",
        f"    if not nonce or len(nonce)>{_NONCE_LIMIT}: raise ValueError",
        "    signal=os.read(gate,1)",
        "    os.close(gate)",
        "    if signal != b'1':",
        "        os.close(data)",
        "        raise SystemExit(1)",
        "    payload=b'READY:'+nonce",
        "    written=os.write(data,payload)",
        "    os.close(data)",
        "    raise SystemExit(0 if written == len(payload) else 1)",
        "except SystemExit:",
        "    raise",
        "except Exception:",
        "    raise SystemExit(1)",
    )
)
_ENV_KEYS = (
    "SystemRoot",
    "WINDIR",
    "COMSPEC",
    "PATH",
    "PATHEXT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "CODEX_HOME",
)


def _environment(
    source: _typing.Mapping[str, str],
    *,
    gate_read: int,
    data_write: int,
    nonce: bytes,
) -> dict[str, str]:
    """Build the child environment without inheriting unrelated metadata."""
    if type(nonce) is not bytes or not 0 < len(nonce) <= _NONCE_LIMIT:
        raise ValueError("invalid readiness nonce")
    try:
        nonce_text = nonce.decode("ascii")
    except UnicodeDecodeError:
        raise ValueError("invalid readiness nonce") from None
    environment = {key: source[key] for key in _ENV_KEYS if key in source}
    environment.update(
        {
            _GATE_ENV: str(gate_read),
            _DATA_ENV: str(data_write),
            _NONCE_ENV: nonce_text,
        }
    )
    return environment


def _startup(
    handles: _typing.Iterable[int],
    factory: _typing.Callable[[], _typing.Any] | None = None,
) -> _typing.Any:
    """Create startup metadata for exactly the child data-write/gate-read pair."""
    child_handles = list(handles)
    if len(child_handles) != 2 or len(set(child_handles)) != 2:
        raise ValueError("directional child handle list must contain two handles")
    try:
        startup = factory() if factory is not None else _subprocess.STARTUPINFO()
        startup.lpAttributeList = {"handle_list": child_handles}
        return startup
    except Exception:
        raise ValueError("invalid startup metadata") from None


def _new_ready_nonce() -> bytes:
    """Generate a non-repeating ASCII-safe nonce for one helper handshake."""
    return _secrets.token_hex(32).encode("ascii")


class _PrimitiveError(RuntimeError):
    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"


class _CleanupError(_PrimitiveError):
    def __init__(self, owner: "_FdCleanup | None" = None) -> None:
        self.owner = owner
        super().__init__("cleanup_failed")


class _OwnershipError(_PrimitiveError):
    pass


class _TimeoutError(_PrimitiveError):
    pass


@_dataclass(frozen=True)
class _AcquisitionEntry:
    close: _typing.Callable[[], None]


class _AcquisitionTransaction:
    def __init__(self) -> None:
        self._entries: list[_AcquisitionEntry] = []
        self._committed = False

    def add(self, close: _typing.Callable[[], None]) -> _AcquisitionEntry:
        if self._committed:
            raise _OwnershipError from None
        entry = _AcquisitionEntry(close)
        self._entries.append(entry)
        return entry

    def release(self, entry: _AcquisitionEntry) -> None:
        index = next((index for index, candidate in enumerate(self._entries) if candidate is entry), None)
        if self._committed or index is None:
            raise _OwnershipError from None
        self._entries.pop(index)

    def rollback(self) -> None:
        if self._committed:
            raise _OwnershipError from None
        with _SPAWN_LOCK:
            failed_execution: list[_AcquisitionEntry] = []
            for entry in reversed(self._entries):
                try:
                    entry.close()
                except Exception:
                    failed_execution.append(entry)
            self._entries = [
                entry
                for entry in self._entries
                if any(entry is failed for failed in failed_execution)
            ]
        if failed_execution:
            raise _CleanupError from None

    def commit(self) -> None:
        if self._committed or self._entries:
            raise _OwnershipError from None
        self._committed = True


def _fd_handle(fd: int) -> int:
    if type(fd) is not int or fd < 0:
        raise _OwnershipError from None
    try:
        import msvcrt

        handle = msvcrt.get_osfhandle(fd)
    except Exception:
        raise _OwnershipError from None
    if type(handle) is not int or handle < 0:
        raise _OwnershipError from None
    return handle


def _set_inheritable(handle: int, inheritable: bool) -> None:
    if type(handle) is not int or handle < 0 or type(inheritable) is not bool:
        raise _OwnershipError from None
    try:
        _os.set_handle_inheritable(handle, inheritable)
    except Exception:
        raise _OwnershipError from None


def _pipe_factory() -> tuple[int, int]:
    return _os.pipe()


class _FdCleanup:
    def __init__(self, closers: _typing.Iterable[_typing.Callable[[], None]]) -> None:
        self._pending = list(closers)
        self._cause: Exception | None = None

    def close(self) -> None:
        failed: list[_typing.Callable[[], None]] = []
        for closer in self._pending:
            try:
                closer()
            except (_IndeterminateCleanupError, _StaleGenerationError) as error:
                self._cause = self._cause or error
                failed.append(closer)
            except Exception:
                failed.append(closer)
        self._pending = failed
        if failed:
            if self._cause is not None:
                raise _CleanupError(self) from self._cause
            raise _CleanupError(self) from None


def _pipes(
    factory: _typing.Callable[[], tuple[int, int]], owner: _OwnerToken
) -> tuple[_IpcPair, _IpcPair, tuple[int, int], tuple[int, int]]:
    gate_read, gate_write = factory()
    registry = _GenerationRegistry()

    def close_fd(identity: _FdIdentity) -> _CloseOutcome:
        result = _os.close(identity._number)
        return result if result is _CloseOutcome.RETRY else _CloseOutcome.CLOSED

    gate_specs = (
        _new_endpoint_spec(gate_read, _GenerationToken(), close_fd),
        _new_endpoint_spec(gate_write, _GenerationToken(), close_fd),
    )
    gate = _new_ipc_pair(gate_specs[0], gate_specs[1], owner, registry)
    try:
        data_read, data_write = factory()
    except Exception:
        _FdCleanup([lambda: gate._close(owner)]).close()
        raise
    data_specs = (
        _new_endpoint_spec(data_read, _GenerationToken(), close_fd),
        _new_endpoint_spec(data_write, _GenerationToken(), close_fd),
    )
    try:
        data = _new_ipc_pair(
            data_specs[0],
            data_specs[1],
            owner,
            registry,
        )
    except Exception:
        _FdCleanup([lambda: gate._close(owner)]).close()
        raise
    return gate, data, (gate_read, gate_write), (data_read, data_write)


class _InheritableHandleReset:
    def __init__(self, set_inheritable: _typing.Callable[[int, bool], object]) -> None:
        self._set_inheritable = set_inheritable
        self._pending: list[int] = []

    def mark(self, handle: int) -> None:
        if type(handle) is not int or handle < 0:
            raise _OwnershipError from None
        self._pending.append(handle)

    def _reset_locked(self) -> None:
        failed: list[int] = []
        for handle in self._pending:
            try:
                self._set_inheritable(handle, False)
            except Exception:
                failed.append(handle)
        self._pending = failed
        if failed:
            raise _CleanupError from None

    def reset(self) -> None:
        with _SPAWN_LOCK:
            self._reset_locked()

    def close(self) -> None:
        self.reset()
