"""Private Codex helper bootstrap/readiness contract."""

import math as _math
import os as _os
import secrets as _secrets
import subprocess as _subprocess
import sys as _sys
import threading as _threading
import time as _time
from dataclasses import dataclass as _dataclass
from enum import Enum as _Enum
import typing as _typing

from .codex_job_resources import _JobAcquisitionFailure, _acquire_job_owner
from .codex_process_resources import _HelperProcessResources, _PopenProcessOwner
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
from .isolation.windows_job import Kernel32Api as _Kernel32Api

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

        return _peek_named_pipe_handle(msvcrt.get_osfhandle(fd))
    except Exception:
        pass
    raise _TransportError("peek_failed") from None


def _peek_named_pipe_handle(handle: int) -> tuple[int, bool]:
    """Peek a pipe using a previously adapted native handle."""
    try:
        import ctypes

        available = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.PeekNamedPipe(
            handle, None, 0, None, ctypes.byref(available), None
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
        reject_trailing: bool = True,
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
            if available < 0:
                raise _TransportError("frame_oversize") from None
            if reject_trailing:
                if available > max_size - len(result):
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
        if reject_trailing:
            available, _ = self._peek(self._read_fd)
            if available:
                raise _TransportError("trailing_data") from None
        return bytes(result)

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
_PROTOCOL_ENV_KEYS = (_GATE_ENV, _DATA_ENV, _NONCE_ENV)


def _environment(
    source: _typing.Mapping[str, str],
    *,
    gate_read: int,
    data_write: int,
    nonce: bytes,
) -> dict[str, str]:
    """Copy the supplied environment and replace only private protocol keys."""
    if type(nonce) is not bytes or not 0 < len(nonce) <= _NONCE_LIMIT:
        raise ValueError("invalid readiness nonce")
    try:
        nonce_text = nonce.decode("ascii")
    except UnicodeDecodeError:
        raise ValueError("invalid readiness nonce") from None
    environment = dict(source)
    for protocol_key in _PROTOCOL_ENV_KEYS:
        for existing_key in tuple(environment):
            if existing_key.casefold() == protocol_key.casefold():
                environment.pop(existing_key)
    environment.update({_GATE_ENV: str(gate_read), _DATA_ENV: str(data_write), _NONCE_ENV: nonce_text})
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


class _AcquisitionError(_PrimitiveError):
    def __init__(
        self,
        owner: object | None = None,
        *,
        primary: Exception | None = None,
        cleanup: Exception | None = None,
    ) -> None:
        self.owner = owner
        self.primary, self.cleanup = primary, cleanup
        super().__init__("acquisition_failed")


class _SupervisorState(str, _Enum):
    OPEN = "open"
    PREPARED = "prepared"
    ACQUIRED = "acquired"
    BROKEN = "broken"
    CLOSED = "closed"


class _PreparedAcquisition:
    def __init__(
        self,
        transaction: "_AcquisitionTransaction",
        owner: _OwnerToken,
        gate: _IpcPair,
        data: _IpcPair,
        descriptors: tuple[tuple[int, int], tuple[int, int]],
        helper: _HelperProcessResources,
        nonce: bytes,
        entries: tuple["_AcquisitionEntry", ...],
    ) -> None:
        self._transaction = transaction
        self._owner = owner
        self._gate, self._data = gate, data
        self._descriptors = descriptors
        self._helper = helper
        self._nonce = nonce
        self._entries = entries

    def rollback(self) -> None:
        self._transaction.rollback()

    def _release_for_commit(self) -> None:
        self._transaction.commit(self._entries)


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
        index = next(
            (
                index
                for index, candidate in enumerate(self._entries)
                if candidate is entry
            ),
            None,
        )
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
                except Exception:  # noqa: BLE001 - retain every cleanup failure
                    failed_execution.append(entry)
            self._entries = [
                entry
                for entry in self._entries
                if any(entry is failed for failed in failed_execution)
            ]
        if failed_execution:
            raise _CleanupError from None

    def commit(self, entries: _typing.Iterable[_AcquisitionEntry] = ()) -> None:
        requested = tuple(entries)
        if self._committed or tuple(self._entries) != requested:
            raise _OwnershipError from None
        self._entries.clear()
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

    def add(self, closer: _typing.Callable[[], None]) -> None:
        self._pending.append(closer)

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

    def close_raw(number: int) -> None:
        result = _os.close(number)
        if result is _CloseOutcome.RETRY:
            raise _CleanupError from None

    def close_unique(
        numbers: _typing.Iterable[int], excluded: _typing.Iterable[int] = ()
    ) -> _FdCleanup:
        seen: set[int] = set(excluded)
        closers = []
        for number in numbers:
            if number not in seen:
                seen.add(number)
                closers.append(lambda number=number: close_raw(number))
        return _FdCleanup(closers)

    gate_specs = (
        _new_endpoint_spec(gate_read, _GenerationToken(), close_fd),
        _new_endpoint_spec(gate_write, _GenerationToken(), close_fd),
    )
    try:
        gate = _new_ipc_pair(gate_specs[0], gate_specs[1], owner, registry)
    except Exception:
        close_unique((gate_write, gate_read)).close()
        raise
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
        data = _new_ipc_pair(data_specs[0], data_specs[1], owner, registry)
    except Exception:
        cleanup = close_unique((data_write, data_read), (gate_read, gate_write))
        cleanup.add(lambda: gate._close(owner))
        cleanup.close()
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


class _CodexSupervisor:
    def __init__(
        self,
        command: _typing.Sequence[str] | None = None,
        *,
        popen_factory: _typing.Callable[..., object] = _subprocess.Popen,
        pipe_factory: _typing.Callable[[], tuple[int, int]] = _pipe_factory,
        handle_adapter: _typing.Callable[[int], int] = _fd_handle,
        set_inheritable: _typing.Callable[[int, bool], object] = _set_inheritable,
        job_factory: _typing.Callable[[object], object] | None = None,
        transport_factory: _typing.Callable[..., _PipeTransport] = _PipeTransport,
        startup_factory: _typing.Callable[[], object] | None = None,
        environment_source: _typing.Mapping[str, str] | None = None,
        timeout_seconds: object = _DEFAULT_TRANSPORT_TIMEOUT,
    ) -> None:
        self._command = (
            tuple(command)
            if command is not None
            else (
                _sys.executable,
                "-I",
                "-S",
                "-E",
                "-c",
                _BOOTSTRAP,
            )
        )
        self._popen_factory, self._pipe_factory = popen_factory, pipe_factory
        self._handle_adapter, self._set_inheritable = handle_adapter, set_inheritable
        self._job_factory = job_factory or _acquire_job_owner
        self._transport_factory = transport_factory
        self._startup_factory = startup_factory
        self._environment_source = dict(_os.environ) if environment_source is None else environment_source
        self._timeout_seconds = timeout_seconds
        self._state = _SupervisorState.OPEN
        self._prepared: _PreparedAcquisition | None = None
        self._pending: _AcquisitionTransaction | None = None
        self._helper = self._gate = self._data = None
        self._owner: _OwnerToken | None = None
        self._nonce: bytes | None = None
        self._terminal_error: Exception | None = None

    def _abort(self, transaction: _AcquisitionTransaction, error: Exception) -> None:
        try:
            transaction.rollback()
        except Exception:  # noqa: BLE001 - preserve the failed owner
            self._pending, self._state = transaction, _SupervisorState.BROKEN
            raise _AcquisitionError(transaction) from error
        raise _AcquisitionError from error

    def acquire(
        self,
        command: _typing.Sequence[str] | None = None,
        nonce: bytes | None = None,
    ) -> "_CodexSupervisor":
        with _SPAWN_LOCK:
            if self._state is not _SupervisorState.OPEN or self._pending is not None:
                raise _OwnershipError from None
            prepared = self._acquire_locked(command, nonce)
            try:
                gate_write = prepared._descriptors[0][1]
                data_read = prepared._descriptors[1][0]
                transport = self._transport_factory(
                    data_read,
                    gate_write,
                    nonblocking=True,
                )
                transport.write_control(
                    b"1",
                    timeout_seconds=self._timeout_seconds,
                )
                expected = b"READY:" + prepared._nonce
                received = transport.read_frame(
                    expected_size=len(expected),
                    timeout_seconds=self._timeout_seconds,
                )
                if received != expected:
                    raise _TransportError("ready_mismatch") from None
                prepared._release_for_commit()
            except Exception as error:  # noqa: BLE001 - retain Unit B cleanup owner
                return self._abort_prepared(prepared, error)
            self._prepared = None
            self._helper, self._gate, self._data = (
                prepared._helper,
                prepared._gate,
                prepared._data,
            )
            self._owner, self._nonce = prepared._owner, prepared._nonce
            self._state = _SupervisorState.ACQUIRED
            return self

    def _abort_prepared(
        self, prepared: _PreparedAcquisition, error: Exception
    ) -> "_CodexSupervisor":
        try:
            prepared.rollback()
        except Exception as cleanup_error:  # noqa: BLE001 - preserve both failures
            self._prepared = None
            self._pending, self._state, self._terminal_error = (
                prepared._transaction,
                _SupervisorState.BROKEN,
                self._terminal_for(prepared._gate)
                or self._terminal_for(prepared._data),
            )
            raise _AcquisitionError(
                self._pending,
                primary=error,
                cleanup=cleanup_error,
            ) from error
        self._prepared = None
        self._state = _SupervisorState.OPEN
        raise _AcquisitionError from error

    def _acquire_locked(
        self,
        command: _typing.Sequence[str] | None,
        nonce: bytes | None,
    ) -> _PreparedAcquisition:
        transaction = _AcquisitionTransaction()
        owner = _OwnerToken()
        try:
            gate, data, gate_descriptors, data_descriptors = _pipes(
                self._pipe_factory, owner
            )
            gate_entry = transaction.add(lambda: gate._close(owner))
            data_entry = transaction.add(lambda: data._close(owner))
            gate_read = gate_descriptors[0]
            data_write = data_descriptors[1]
            gate_handle = self._handle_adapter(gate_read)
            data_handle = self._handle_adapter(data_write)
            startup = (
                _startup([data_handle, gate_handle], self._startup_factory)
                if _os.name == "nt" or self._startup_factory is not None
                else None
            )
            if nonce is None:
                nonce = _new_ready_nonce()
            environment = _environment(
                self._environment_source,
                gate_read=gate_handle,
                data_write=data_handle,
                nonce=nonce,
            )
            resetter = _InheritableHandleReset(self._set_inheritable)
            reset_entry = transaction.add(resetter.close)
            for handle in (gate_handle, data_handle):
                resetter.mark(handle)
                self._set_inheritable(handle, True)
            popen_kwargs = {
                "env": environment,
                "startupinfo": startup,
                "close_fds": True,
                "stdin": _subprocess.DEVNULL,
                "stdout": _subprocess.DEVNULL,
                "stderr": _subprocess.DEVNULL,
            }
            if _os.name == "nt": popen_kwargs["creationflags"] = _subprocess.CREATE_BREAKAWAY_FROM_JOB
            if _os.name != "nt":
                popen_kwargs["pass_fds"] = (gate_read, data_write)
            popen = self._popen_factory(
                list(command if command is not None else self._command),
                **popen_kwargs,
            )
            process_owner = _PopenProcessOwner.register(popen)
            process_entry = transaction.add(process_owner.close)
            resetter.reset()
            transaction.release(reset_entry)
            gate._read._close()
            data._write._close()
            process_owner.adapt_native_handle()
            job = self._job_factory(_Kernel32Api.load() if _os.name == "nt" else None)
            job_entry = transaction.add(job.close)
            helper = _HelperProcessResources(process_owner)
            helper.attach_job(job)
            transaction.release(process_entry)
            transaction.release(job_entry)
            helper_entry = transaction.add(helper.close)
            prepared = _PreparedAcquisition(
                transaction,
                owner,
                gate,
                data,
                (gate_descriptors, data_descriptors),
                helper,
                nonce,
                (gate_entry, data_entry, helper_entry),
            )
            self._prepared, self._state = prepared, _SupervisorState.PREPARED
            return prepared
        except _JobAcquisitionFailure as error:
            if error.owner is not None:
                transaction.add(error.owner.close)
            return self._abort(transaction, error)
        except Exception as error:  # noqa: BLE001 - rollback every acquisition failure
            owner_to_retain = getattr(error, "owner", None)
            if owner_to_retain is not None:
                transaction.add(owner_to_retain.close)
            return self._abort(transaction, error)

    def close(self, timeout_seconds: object = _DEFAULT_TRANSPORT_TIMEOUT) -> None:
        with _SPAWN_LOCK:
            if self._pending is not None:
                try:
                    self._pending.rollback()
                except Exception as error:
                    raise _AcquisitionError(self._pending) from error
                self._pending = None
                if (
                    self._prepared is None
                    and self._helper is None
                    and self._terminal_error is None
                ):
                    self._state = _SupervisorState.CLOSED
                    return
            if self._state is _SupervisorState.CLOSED:
                return
            if self._prepared is not None:
                try:
                    self._prepared.rollback()
                except Exception as error:
                    self._pending = self._prepared._transaction
                    self._prepared = None
                    self._state = _SupervisorState.BROKEN
                    raise _AcquisitionError(self._pending) from error
                self._prepared = None
                self._state = _SupervisorState.CLOSED
                return
            failures: list[Exception] = []
            for resource, closer in (
                (self._helper, lambda: self._helper.close(timeout_seconds)),
                (self._data, lambda: self._data._close(self._owner)),
                (self._gate, lambda: self._gate._close(self._owner)),
            ):
                if resource is None:
                    continue
                try:
                    closer()
                except Exception as error:  # noqa: BLE001 - retry bounded cleanup
                    failures.append(error)
                terminal = self._terminal_for(resource)
                if terminal is not None and self._terminal_error is None:
                    self._terminal_error = terminal
            if self._terminal_error is not None:
                self._state = _SupervisorState.BROKEN
                raise _AcquisitionError(
                    self,
                    primary=self._terminal_error,
                    cleanup=failures[0] if failures else None,
                ) from self._terminal_error
            if failures:
                self._state = _SupervisorState.BROKEN
                raise _AcquisitionError(self) from failures[0]
            self._helper = self._gate = self._data = self._owner = self._nonce = None
            self._state = _SupervisorState.CLOSED

    @staticmethod
    def _terminal_for(resource: object) -> Exception | None:
        for endpoint in (
            getattr(resource, "_read", None),
            getattr(resource, "_write", None),
        ):
            if endpoint is not None and endpoint._state.value == "terminal":
                return getattr(endpoint, "_terminal_error", None)
        return None
