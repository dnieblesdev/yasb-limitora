"""Lexical, lookup-free path contracts used by the JSON contract."""

# ruff: noqa: BLE001

from __future__ import annotations

import ctypes
import multiprocessing
import ntpath
import os
import queue
import stat
import sys
from contextlib import ExitStack, suppress
from typing import Any, cast

from .deadline import DeadlineContext

MAX_PATH_UTF16_UNITS = 32_767


class PathError(ValueError):
    """Raised when a local path is outside the safe local-path contract."""


class FileError(PathError):
    """Raised when bounded configuration I/O cannot complete safely."""


class DeadlineError(FileError):
    """Raised when configuration I/O reaches the reserve-excluding endpoint."""


MAX_CONFIG_BYTES = 16_384
CONFIG_READ_PROBE_BYTES = MAX_CONFIG_BYTES + 1

_PUBLIC_CHILD_ENV_KEYS = frozenset(
    {
        "ALLUSERSPROFILE", "APPDATA", "COMSPEC", "HOMEDRIVE", "HOMEPATH",
        "LANG", "LC_ALL", "LC_CTYPE", "LOCALAPPDATA", "NUMBER_OF_PROCESSORS",
        "OS", "PATH", "PATHEXT", "PROCESSOR_ARCHITECTURE", "PROCESSOR_IDENTIFIER",
        "PROGRAMDATA", "SYSTEMDRIVE", "SYSTEMROOT", "TEMP", "TERM", "TMP",
        "USERDOMAIN", "USERNAME", "USERPROFILE", "WINDIR",
    }
)
_PYINSTALLER_CHILD_ENV_KEYS = frozenset(
    {"_PYI_ARCHIVE_FILE", "_PYI_APPLICATION_HOME_DIR", "_PYI_PARENT_PROCESS_LEVEL"}
)
_MULTIPROCESSING_CONTEXT: Any = cast(Any, vars(multiprocessing)["context"])
_PRIVATE_SYS: Any = cast(Any, sys)
_PENDING_JOB_OWNERS: list[object] = []
_PENDING_PROCESS_OWNERS: list[tuple[object, bool]] = []
_PENDING_IPC_OWNERS: list[tuple[object, bool]] = []
def _retain_job_owner(job: object) -> None:
    if not any(candidate is job for candidate in _PENDING_JOB_OWNERS):
        _PENDING_JOB_OWNERS.append(job)

def _close_job_owner(job: object, context) -> bool:
    try:
        close = cast(Any, job).close_with_deadline
        close(context)
    except Exception:
        _retain_job_owner(job)
        return False
    return True
def _retry_pending_job_owners(context) -> bool:
    remaining = []
    for job in _PENDING_JOB_OWNERS:
        if not _close_job_owner(job, context):
            remaining.append(job)
    _PENDING_JOB_OWNERS[:] = remaining
    return not remaining
def _retain_process_owner(process: object, started: bool) -> None:
    if not any(candidate is process for candidate, _ in _PENDING_PROCESS_OWNERS):
        _PENDING_PROCESS_OWNERS.append((process, started))
def _close_process_owner(process: Any, context, started: bool) -> bool:
    try:
        if started and not _terminate_child(process, context):
            raise RuntimeError
        process.close()
    except Exception:
        _retain_process_owner(process, started)
        return False
    return True
def _retry_pending_process_owners(context) -> bool:
    remaining = []
    for process, started in _PENDING_PROCESS_OWNERS:
        if not _close_process_owner(process, context, started):
            remaining.append((process, started))
    _PENDING_PROCESS_OWNERS[:] = remaining
    return not remaining
def _retain_ipc_owner(endpoint: object, output: bool) -> None:
    if not any(candidate is endpoint for candidate, _ in _PENDING_IPC_OWNERS):
        _PENDING_IPC_OWNERS.append((endpoint, output))
def _retry_pending_ipc_owners(context) -> bool:
    remaining = []
    for endpoint, output in _PENDING_IPC_OWNERS:
        ok = _close_output(endpoint, context, retain=False) if output else _close_ipc_endpoint(endpoint, context, retain=False)
        if not ok:
            remaining.append((endpoint, output))
    _PENDING_IPC_OWNERS[:] = remaining
    return not remaining
def _windows_full_path(value: str) -> str | None:
    if os.name != "nt":
        return None
    # GetFullPathNameW rejects some paths at the documented boundary even
    # though the normalized lexical contract permits exactly 32,767 units.
    # Absolute drive paths need no current-directory lookup, so normalize
    # those at the boundary with the same lexical rules instead.
    if ntpath.splitdrive(value)[0] and len(value.encode("utf-16-le")) // 2 >= MAX_PATH_UTF16_UNITS - 7:
        return None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_full_path = kernel32.GetFullPathNameW
    get_full_path.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_wchar_p)]
    get_full_path.restype = ctypes.c_uint32
    size = 512
    while size <= MAX_PATH_UTF16_UNITS + 1:
        buffer = ctypes.create_unicode_buffer(size)
        result = get_full_path(value, size, buffer, None)
        if result == 0:
            raise PathError("invalid path")
        if result < size - 1:
            return buffer.value
        size = result + 1
    raise PathError("path is too long")


def _lexical_full_path(value: str) -> str:
    windows_value = _windows_full_path(value)
    if windows_value is not None:
        return ntpath.normpath(windows_value.replace("/", "\\"))
    if os.name != "nt" and value.startswith("/"):
        return os.path.normpath(os.path.abspath(value))
    if ntpath.splitdrive(value)[0] or value.startswith(("\\", "/")):
        return ntpath.normpath(value.replace("/", "\\"))
    return os.path.normpath(os.path.abspath(value))


def canonicalize_path(path: object) -> str:
    """Return a normalized effective path without checking the filesystem."""

    if not isinstance(path, str) or not path:
        raise PathError("invalid path")
    lexical = path if os.name != "nt" and path.startswith("/") else path.replace("/", "\\")
    rejection_form = path.replace("/", "\\")
    if rejection_form.startswith(("\\\\?\\", "\\\\.\\", "\\\\")):
        raise PathError("non-local path")
    canonical = _lexical_full_path(lexical)
    if len(canonical.encode("utf-16-le")) // 2 > MAX_PATH_UTF16_UNITS:
        raise PathError("path is too long")
    return canonical


def path_identity(path: object) -> str:
    """Return the opaque-independent case-insensitive lexical identity."""

    return canonicalize_path(path).casefold()


def _remaining_or_fail(context: DeadlineContext) -> None:
    if context.remaining_ns() <= 0:
        raise FileError("configuration read failed")


def _usable_or_fail(context: DeadlineContext) -> None:
    if context.usable_ns() <= 0:
        raise DeadlineError("configuration deadline exhausted")


def _close_output(output: Any, context: DeadlineContext, *, retain: bool = True) -> bool:
    ok = True
    try:
        output.close()
    except Exception:
        ok = False
    thread = getattr(output, "_thread", None)
    if thread is not None:
        try:
            thread.join(max(0.0, context.cleanup_ns() / 1_000_000_000))
            if thread.is_alive():
                cancel = getattr(output, "cancel_join_thread", None)
                if cancel is None:
                    ok = False
                else:
                    try:
                        cancel()
                    except Exception:
                        ok = False
                ok = False
        except Exception:
            ok = False
        if not ok and retain:
            _retain_ipc_owner(output, True)
        return ok
    cancel = getattr(output, "cancel_join_thread", None)
    if cancel is not None:
        try:
            cancel()
        except Exception:
            ok = False
    join_thread = getattr(output, "join_thread", None)
    if join_thread is not None:
        try:
            join_thread()
        except Exception:
            ok = False
    if not ok and retain:
        _retain_ipc_owner(output, True)
    return ok


def _close_ipc_endpoint(endpoint: object, context: DeadlineContext | None = None, *, retain: bool = True) -> bool:
    close = getattr(endpoint, "close", None)
    if close is None:
        return True
    ok = True
    try:
        close()
    except Exception:
        ok = False
    if context is not None:
        cancel = getattr(endpoint, "cancel_join_thread", None)
        if cancel is not None:
            try:
                cancel()
            except Exception:
                ok = False
    if not ok and retain:
        _retain_ipc_owner(endpoint, False)
    return ok


def _silence_child_stderr() -> None:
    try:
        sys.stderr = open(os.devnull, "w", encoding="ascii")  # noqa: SIM115 - retained for child lifetime
    except Exception:
        return


def _public_child_environment(source) -> dict[str, str]:
    return {
        key: value
        for key, value in source.items()
        if isinstance(key, str)
        and isinstance(value, str)
        and key.upper() in _PUBLIC_CHILD_ENV_KEYS
    }


def _private_child_environment(source) -> dict[str, str]:
    environment = _public_child_environment(source)
    if getattr(_PRIVATE_SYS, "frozen", False):
        environment.update(
            {
                key: value
                for key, value in source.items()
                if key in _PYINSTALLER_CHILD_ENV_KEYS and isinstance(value, str)
            }
        )
    return environment


def _windows_spawn_executable(python_exe: str, *, replace_with_base: bool, base_executable: str) -> str:
    if getattr(_PRIVATE_SYS, "frozen", False) or not replace_with_base:
        return python_exe
    return base_executable


def _windows_spawn_popen(process_obj: object) -> Any:
    """Use CreateProcess with a private, already-filtered environment."""
    stdlib = cast(Any, __import__("multiprocessing.popen_spawn_win32", fromlist=["*"]))
    private_process = cast(Any, process_obj)
    class PrivatePopen(stdlib.Popen):
        def __init__(self, process_obj: Any):
            prep_data = stdlib.spawn.get_preparation_data(private_process._name)
            rhandle, whandle = stdlib._winapi.CreatePipe(None, 0)
            wfd = stdlib.msvcrt.open_osfhandle(whandle, 0)
            cmd = stdlib.spawn.get_command_line(parent_pid=os.getpid(), pipe_handle=rhandle)
            cmd = " ".join(f'"{item}"' for item in cmd)
            python_exe = stdlib.spawn.get_executable()
            environment = dict(private_process._child_environment)
            replace_with_base = stdlib.WINENV and stdlib._path_eq(python_exe, sys.executable)
            python_exe = _windows_spawn_executable(
                python_exe, replace_with_base=replace_with_base, base_executable=_PRIVATE_SYS._base_executable
            )
            if replace_with_base and not getattr(_PRIVATE_SYS, "frozen", False):
                environment["__PYVENV_LAUNCHER__"] = sys.executable
            with ExitStack() as stack:
                try:
                    to_child = stack.enter_context(open(wfd, "wb", closefd=True))
                except BaseException:
                    stdlib._winapi.CloseHandle(rhandle)
                    with suppress(OSError):
                        os.close(wfd)
                    raise
                try:
                    hp, ht, pid, _tid = stdlib._winapi.CreateProcess(
                        python_exe, cmd, None, None, False, 0, environment, None, None
                    )
                    stdlib._winapi.CloseHandle(ht)
                except BaseException:
                    stdlib._winapi.CloseHandle(rhandle)
                    raise
                try:
                    sentinel = int(hp)
                    rhandle_value = int(rhandle)
                except (TypeError, ValueError, OverflowError):
                    stdlib._winapi.CloseHandle(hp)
                    stdlib._winapi.CloseHandle(rhandle)
                    raise
                self.pid = pid
                self.returncode = None
                self._handle = hp
                self.sentinel = sentinel
                self.finalizer = stdlib.util.Finalize(
                    self, stdlib._close_handles, (sentinel, rhandle_value)
                )
                stdlib.set_spawning_popen(self)
                try:
                    stdlib.reduction.dump(prep_data, to_child)
                    stdlib.reduction.dump(process_obj, to_child)
                finally:
                    stdlib.set_spawning_popen(None)
    return PrivatePopen(process_obj)
class _WindowsSpawnProcess(_MULTIPROCESSING_CONTEXT.SpawnProcess):
    @staticmethod
    def _Popen(process_obj: object) -> Any:
        return _windows_spawn_popen(process_obj)
def _is_genuine_windows_spawn_context(process_context: object) -> bool:
    return os.name == "nt" and isinstance(process_context, _MULTIPROCESSING_CONTEXT.SpawnContext)


def _child_process(process_context: Any, target: Any, args: Any, process_factory: Any = None) -> Any:
    if process_factory is not None:
        return process_factory(target=target, args=args)
    if _is_genuine_windows_spawn_context(process_context):
        process = cast(Any, _WindowsSpawnProcess(target=target, args=args))
        process._child_environment = _private_child_environment(os.environ)
        return process
    return process_context.Process(target=target, args=args)


def _start_quiet_child(process: Any) -> None:
    """Prevent multiprocessing bootstrap diagnostics from crossing the boundary."""
    original_stderr = sys.stderr
    original_system_stderr = getattr(sys, "__stderr__", None)
    try:
        with open(os.devnull, "w", encoding="ascii") as stream:
            sys.stderr = stream
            sys.__stderr__ = stream
            process.start()
    finally:
        sys.stderr = original_stderr
        sys.__stderr__ = original_system_stderr


def _queue_put(output: Any, value: object) -> None:
    with suppress(Exception):
        output.put(value)


def _terminate_child(process: Any, context: DeadlineContext) -> bool:
    """Stop a timed-out child and confirm it is no longer alive."""
    try:
        if not process.is_alive():
            return True
        with suppress(Exception):
            process.terminate()
        process.join(max(0.0, context.cleanup_ns() / 1_000_000_000))
        if process.is_alive():
            kill = getattr(process, "kill", None)
            if kill is not None:
                kill()
                process.join(max(0.0, context.cleanup_ns() / 1_000_000_000))
        return not process.is_alive()
    except Exception:
        return False


def _file_call_child(function, args, authorized, output) -> None:
    _silence_child_stderr()
    try:
        authorized.wait()
        output.send((True, function(*args)))
    except Exception:
        with suppress(Exception):
            output.send((False, None))
    finally:
        _close_ipc_endpoint(output)


def _file_read_child(path: str, authorized, output) -> None:
    _silence_child_stderr()
    descriptor = None
    try:
        authorized.wait()
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_CONFIG_BYTES:
            _queue_put(output, (False, None))
            return
        data = os.read(descriptor, CONFIG_READ_PROBE_BYTES)
        _queue_put(output, (isinstance(data, bytes) and len(data) <= MAX_CONFIG_BYTES, data))
    except Exception:
        _queue_put(output, (False, None))
    finally:
        if descriptor is not None:
            with suppress(Exception):
                os.close(descriptor)
        _close_ipc_endpoint(output)


def _bounded_file_read(path: str, context) -> bytes:
    _usable_or_fail(context)
    if not _retry_pending_process_owners(context) or not _retry_pending_job_owners(context) or not _retry_pending_ipc_owners(context):
        raise FileError("configuration read failed")
    output = None
    authorized = None
    process = None
    job = None
    process_started = False
    process_close_attempted = False
    job_close_attempted = False
    cleanup_failed = False
    failure: FileError | DeadlineError | None = None
    success = False
    data: object = None
    try:
        method = "fork" if "fork" in multiprocessing.get_all_start_methods() else "spawn"
        process_context = multiprocessing.get_context(method)
        output = process_context.Queue()
        authorized = process_context.Event()
        process = _child_process(process_context, _file_read_child, (path, authorized, output))
        _start_quiet_child(process)
        process_started = True
        if os.name == "nt":
            job = __import__("yasb_limitora.isolation.windows_job", fromlist=["WindowsJobBoundary"]).WindowsJobBoundary()
            job.assign_process(process.pid, allow_nested=True)
        _usable_or_fail(context)
        authorized.set()
        process.join(min(context.usable_ns() / 1_000_000_000, 0.1))
        if process.is_alive():
            try:
                success, data = output.get(timeout=context.usable_ns() / 1_000_000_000)
            except queue.Empty:
                if job is not None:
                    job_close_attempted = True
                    cleanup_failed = not _close_job_owner(job, context)
                raise DeadlineError("configuration deadline exhausted") from None
            process.join(max(0.0, context.usable_ns() / 1_000_000_000))
        else:
            success, data = output.get_nowait()
        if process.is_alive():
            raise FileError("configuration read failed")
        if job is not None:
            job_close_attempted = True
            cleanup_failed = not _close_job_owner(job, context)
        _usable_or_fail(context)
        if not success:
            raise FileError("configuration read failed")
    except FileError as error:
        failure = error
    except Exception:
        failure = FileError("configuration read failed")
    finally:
        if job is not None and not job_close_attempted:
            job_close_attempted = True
            cleanup_failed = not _close_job_owner(job, context) or cleanup_failed
        if process is not None and not process_close_attempted:
            process_close_attempted = True
            cleanup_failed = not _close_process_owner(process, context, process_started) or cleanup_failed
        if output is not None:
            cleanup_failed = not _close_output(output, context) or cleanup_failed
    if cleanup_failed:
        raise FileError("configuration read failed")
    if failure is not None:
        raise failure
    if not isinstance(data, bytes):
        raise FileError("configuration read failed")
    return data


def _bounded_file_call(function, args, context):
    """Run an injectable potentially-blocking file primitive behind a deadline."""
    _usable_or_fail(context)
    if not _retry_pending_process_owners(context) or not _retry_pending_job_owners(context) or not _retry_pending_ipc_owners(context):
        raise FileError("configuration read failed")
    receiver = None
    sender = None
    authorized = None
    process = None
    job = None
    process_started = False
    process_close_attempted = False
    job_close_attempted = False
    cleanup_failed = False
    failure: FileError | DeadlineError | None = None
    value: Any = None
    try:
        method = "fork" if "fork" in multiprocessing.get_all_start_methods() else "spawn"
        process_context = multiprocessing.get_context(method)
        receiver, sender = process_context.Pipe(duplex=False)
        authorized = process_context.Event()
        process = _child_process(process_context, _file_call_child, (function, args, authorized, sender))
        _start_quiet_child(process)
        process_started = True
        cleanup_failed = not _close_ipc_endpoint(sender) or cleanup_failed
        sender = None
        if os.name == "nt":
            job = __import__("yasb_limitora.isolation.windows_job", fromlist=["WindowsJobBoundary"]).WindowsJobBoundary()
            job.assign_process(process.pid, allow_nested=True)
        _usable_or_fail(context)
        authorized.set()
        process.join(context.usable_ns() / 1_000_000_000)
        if process.is_alive():
            raise DeadlineError("configuration deadline exhausted")
        if context.usable_ns() <= 0 or not receiver.poll():
            raise DeadlineError("configuration deadline exhausted")
        success, value = receiver.recv()
        if not success:
            raise FileError("configuration read failed")
        if job is not None:
            job_close_attempted = True
            cleanup_failed = not _close_job_owner(job, context)
    except FileError as error:
        failure = error
    except Exception:
        failure = FileError("configuration read failed")
    finally:
        if job is not None and not job_close_attempted:
            job_close_attempted = True
            cleanup_failed = not _close_job_owner(job, context) or cleanup_failed
        if process is not None and not process_close_attempted:
            process_close_attempted = True
            cleanup_failed = not _close_process_owner(process, context, process_started) or cleanup_failed
        if receiver is not None:
            cleanup_failed = not _close_ipc_endpoint(receiver) or cleanup_failed
        if sender is not None:
            cleanup_failed = not _close_ipc_endpoint(sender) or cleanup_failed
        if authorized is not None:
            cleanup_failed = not _close_ipc_endpoint(authorized, context) or cleanup_failed
    if cleanup_failed:
        raise FileError("configuration read failed")
    if failure is not None:
        raise failure
    return value


def read_config(
    path: object,
    context: DeadlineContext,
    *,
    stat_fn=os.stat,
    open_fn=os.open,
    read_fn=os.read,
    close_fn=os.close,
) -> bytes:
    """Read one regular local file with a bounded extra-byte probe."""

    try:
        _usable_or_fail(context)
        if not _retry_pending_process_owners(context) or not _retry_pending_job_owners(context) or not _retry_pending_ipc_owners(context):
            raise FileError("configuration read failed")
        source_path = os.fspath(path) if isinstance(path, os.PathLike) else path
        canonical = canonicalize_path(source_path)
        if stat_fn is os.stat and open_fn is os.open and read_fn is os.read and close_fn is os.close:
            return _bounded_file_read(canonical, context)
        _usable_or_fail(context)
        metadata = stat_fn(canonical)
        if not stat.S_ISREG(metadata.st_mode):
            raise FileError("configuration read failed")
        if metadata.st_size > MAX_CONFIG_BYTES:
            raise FileError("configuration read failed")
        _usable_or_fail(context)
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        descriptor = open_fn(canonical, flags)
    except FileError:
        raise
    except Exception as error:  # No path or OS detail crosses the boundary.
        raise FileError("configuration read failed") from error

    data: bytes | None = None
    failure: BaseException | None = None
    try:
        _usable_or_fail(context)
        if read_fn is os.read:
            data = read_fn(descriptor, CONFIG_READ_PROBE_BYTES)
        else:
            data = _bounded_file_call(read_fn, (descriptor, CONFIG_READ_PROBE_BYTES), context)
        if not isinstance(data, bytes) or len(data) > MAX_CONFIG_BYTES:
            raise FileError("configuration read failed")
    except BaseException as error:  # Cleanup must run for every failure.
        failure = error
    finally:
        try:
            if close_fn is os.close:
                close_fn(descriptor)
            else:
                # The child cannot close the parent's descriptor. Run the
                # injected close behind the deadline, then close the owned
                # descriptor locally regardless of the injected outcome.
                try:
                    _usable_or_fail(context)
                    _bounded_file_call(close_fn, (descriptor,), context)
                finally:
                    with suppress(OSError):
                        os.close(descriptor)
            _usable_or_fail(context)
        except BaseException as error:  # Cleanup failures are sanitized.
            if failure is None:
                failure = error
    if failure is not None:
        if isinstance(failure, FileError):
            raise failure
        raise FileError("configuration read failed") from failure
    return data if data is not None else b""


__all__ = (
    "CONFIG_READ_PROBE_BYTES",
    "MAX_CONFIG_BYTES",
    "MAX_PATH_UTF16_UNITS",
    "DeadlineError",
    "FileError",
    "PathError",
    "canonicalize_path",
    "path_identity",
    "read_config",
)
