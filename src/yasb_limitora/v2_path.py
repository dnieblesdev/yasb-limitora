"""Lexical, lookup-free path contracts used by JSON v2."""

from __future__ import annotations

import ctypes
import multiprocessing
import ntpath
import os
import queue
import stat

from .v2_deadline import DeadlineContext


MAX_PATH_UTF16_UNITS = 32_767


class V2PathError(ValueError):
    """Raised when a v2 path is outside the safe local-path contract."""


class V2FileError(V2PathError):
    """Raised when bounded v2 configuration I/O cannot complete safely."""


class V2DeadlineError(V2FileError):
    """Raised when configuration I/O reaches the reserve-excluding endpoint."""


MAX_CONFIG_BYTES = 16_384
CONFIG_READ_PROBE_BYTES = MAX_CONFIG_BYTES + 1


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
            raise V2PathError("invalid path")
        if result < size - 1:
            return buffer.value
        size = result + 1
    raise V2PathError("path is too long")


def _lexical_full_path(value: str) -> str:
    windows_value = _windows_full_path(value)
    if windows_value is not None:
        return ntpath.normpath(windows_value.replace("/", "\\"))
    if os.name != "nt" and value.startswith("/"):
        return os.path.normpath(os.path.abspath(value))
    if ntpath.splitdrive(value)[0] or value.startswith(("\\", "/")):
        return ntpath.normpath(value.replace("/", "\\"))
    return os.path.normpath(os.path.abspath(value))


def canonicalize_v2_path(path: object) -> str:
    """Return a normalized effective path without checking the filesystem."""

    if not isinstance(path, str) or not path:
        raise V2PathError("invalid path")
    lexical = path if os.name != "nt" and path.startswith("/") else path.replace("/", "\\")
    if lexical.startswith(("\\\\?\\", "\\\\.\\", "\\\\")):
        raise V2PathError("non-local path")
    canonical = _lexical_full_path(lexical)
    if len(canonical.encode("utf-16-le")) // 2 > MAX_PATH_UTF16_UNITS:
        raise V2PathError("path is too long")
    return canonical


def path_identity(path: object) -> str:
    """Return the opaque-independent case-insensitive lexical identity."""

    return canonicalize_v2_path(path).casefold()


def _remaining_or_fail(context: DeadlineContext) -> None:
    if context.remaining_ns() <= 0:
        raise V2FileError("configuration read failed")


def _usable_or_fail(context: DeadlineContext) -> None:
    if context.usable_ns() <= 0:
        raise V2DeadlineError("configuration deadline exhausted")


def _close_output(output: object, context: DeadlineContext) -> None:
    output.close()
    thread = getattr(output, "_thread", None)
    if thread is not None:
        thread.join(max(0.0, context.cleanup_ns() / 1_000_000_000))
        if thread.is_alive():
            output.cancel_join_thread()
        return
    cancel = getattr(output, "cancel_join_thread", None)
    if cancel is not None:
        cancel()
    join_thread = getattr(output, "join_thread", None)
    if join_thread is not None:
        join_thread()


def _file_call_child(function, args, output) -> None:
    try:
        output.send((True, function(*args)))
    except Exception:
        output.send((False, None))
    finally:
        output.close()


def _file_read_child(path: str, authorized, output) -> None:
    descriptor = None
    try:
        authorized.wait()
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_CONFIG_BYTES:
            output.put((False, None))
            return
        data = os.read(descriptor, CONFIG_READ_PROBE_BYTES)
        output.put((isinstance(data, bytes) and len(data) <= MAX_CONFIG_BYTES, data))
    except Exception:
        output.put((False, None))
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except Exception:
                pass
        output.close()


def _bounded_file_read(path: str, context) -> bytes:
    _usable_or_fail(context)
    output = None
    process = None
    job = None
    try:
        method = "fork" if "fork" in multiprocessing.get_all_start_methods() else "spawn"
        process_context = multiprocessing.get_context(method)
        output = process_context.Queue()
        authorized = process_context.Event()
        process = process_context.Process(target=_file_read_child, args=(path, authorized, output))
        process.start()
        if os.name == "nt":
            job = __import__("yasb_limitora.isolation.windows_job", fromlist=["WindowsJobBoundary"]).WindowsJobBoundary()
            job.assign_process(process.pid)
        authorized.set()
        process.join(min(context.usable_ns() / 1_000_000_000, 0.1))
        if process.is_alive():
            try:
                success, data = output.get(timeout=context.usable_ns() / 1_000_000_000)
            except queue.Empty:
                if job is not None:
                    job.close_with_deadline(context)
                else:
                    process.terminate()
                    process.join(max(0.0, context.cleanup_ns() / 1_000_000_000))
                raise V2DeadlineError("configuration deadline exhausted")
            process.join(max(0.0, context.usable_ns() / 1_000_000_000))
        else:
            success, data = output.get_nowait()
        if process.is_alive():
            raise V2FileError("configuration read failed")
        if job is not None:
            job.close_with_deadline(context)
        _usable_or_fail(context)
        if not success or not isinstance(data, bytes):
            raise V2FileError("configuration read failed")
        return data
    except V2FileError:
        raise
    except Exception:
        raise V2FileError("configuration read failed") from None
    finally:
        if process is not None and process.is_alive():
            try:
                process.terminate()
                process.join(max(0.0, context.cleanup_ns() / 1_000_000_000))
            except Exception:
                pass
        if output is not None:
            _close_output(output, context)


def _bounded_file_call(function, args, context):
    """Run an injectable potentially-blocking file primitive behind a deadline."""
    _usable_or_fail(context)
    try:
        method = "fork" if "fork" in multiprocessing.get_all_start_methods() else "spawn"
        process_context = multiprocessing.get_context(method)
        receiver, sender = process_context.Pipe(duplex=False)
        process = process_context.Process(target=_file_call_child, args=(function, args, sender))
        process.start()
        sender.close()
        process.join(context.usable_ns() / 1_000_000_000)
        if process.is_alive():
            process.terminate()
            process.join(max(0.0, context.cleanup_ns() / 1_000_000_000))
            raise V2DeadlineError("configuration deadline exhausted")
        if context.usable_ns() <= 0 or not receiver.poll():
            raise V2DeadlineError("configuration deadline exhausted")
        success, value = receiver.recv()
        if not success:
            raise V2FileError("configuration read failed")
        return value
    except V2FileError:
        raise
    except Exception:
        raise V2FileError("configuration read failed") from None
    finally:
        try:
            receiver.close()
        except Exception:
            pass


def read_v2_config(
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
        source_path = os.fspath(path) if isinstance(path, os.PathLike) else path
        canonical = canonicalize_v2_path(source_path)
        if stat_fn is os.stat and open_fn is os.open and read_fn is os.read and close_fn is os.close:
            return _bounded_file_read(canonical, context)
        _usable_or_fail(context)
        metadata = stat_fn(canonical)
        if not stat.S_ISREG(metadata.st_mode):
            raise V2FileError("configuration read failed")
        if metadata.st_size > MAX_CONFIG_BYTES:
            raise V2FileError("configuration read failed")
        _usable_or_fail(context)
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        descriptor = open_fn(canonical, flags)
    except V2FileError:
        raise
    except Exception as error:  # noqa: BLE001 - no path or OS detail crosses the boundary
        raise V2FileError("configuration read failed") from error

    data: bytes | None = None
    failure: BaseException | None = None
    try:
        _usable_or_fail(context)
        if read_fn is os.read:
            data = read_fn(descriptor, CONFIG_READ_PROBE_BYTES)
        else:
            data = _bounded_file_call(read_fn, (descriptor, CONFIG_READ_PROBE_BYTES), context)
        if not isinstance(data, bytes) or len(data) > MAX_CONFIG_BYTES:
            raise V2FileError("configuration read failed")
    except BaseException as error:  # noqa: BLE001 - cleanup must run for every failure
        failure = error
    finally:
        try:
            _usable_or_fail(context)
            if close_fn is os.close:
                close_fn(descriptor)
            else:
                # The child cannot close the parent's descriptor. Run the
                # injected close behind the deadline, then close the owned
                # descriptor locally regardless of the injected outcome.
                try:
                    _bounded_file_call(close_fn, (descriptor,), context)
                finally:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass
        except BaseException as error:  # noqa: BLE001 - cleanup failures are sanitized
            if failure is None:
                failure = error
    if failure is not None:
        if isinstance(failure, V2FileError):
            raise failure
        raise V2FileError("configuration read failed") from failure
    return data if data is not None else b""


__all__ = (
    "CONFIG_READ_PROBE_BYTES",
    "MAX_CONFIG_BYTES",
    "MAX_PATH_UTF16_UNITS",
    "V2DeadlineError",
    "V2FileError",
    "V2PathError",
    "canonicalize_v2_path",
    "path_identity",
    "read_v2_config",
)
