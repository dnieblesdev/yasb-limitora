"""Lexical, lookup-free path contracts used by JSON v2."""

from __future__ import annotations

import ctypes
import ntpath
import os
import stat

from .v2_deadline import DeadlineContext


MAX_PATH_UTF16_UNITS = 32_767


class V2PathError(ValueError):
    """Raised when a v2 path is outside the safe local-path contract."""


class V2FileError(V2PathError):
    """Raised when bounded v2 configuration I/O cannot complete safely."""


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
        _remaining_or_fail(context)
        metadata = stat_fn(canonical)
        if not stat.S_ISREG(metadata.st_mode):
            raise V2FileError("configuration read failed")
        if metadata.st_size > MAX_CONFIG_BYTES:
            raise V2FileError("configuration read failed")
        _remaining_or_fail(context)
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        descriptor = open_fn(canonical, flags)
    except V2FileError:
        raise
    except Exception as error:  # noqa: BLE001 - no path or OS detail crosses the boundary
        raise V2FileError("configuration read failed") from error

    data: bytes | None = None
    failure: BaseException | None = None
    try:
        _remaining_or_fail(context)
        data = read_fn(descriptor, CONFIG_READ_PROBE_BYTES)
        if not isinstance(data, bytes) or len(data) > MAX_CONFIG_BYTES:
            raise V2FileError("configuration read failed")
    except BaseException as error:  # noqa: BLE001 - cleanup must run for every failure
        failure = error
    finally:
        try:
            _remaining_or_fail(context)
            close_fn(descriptor)
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
    "V2FileError",
    "V2PathError",
    "canonicalize_v2_path",
    "path_identity",
    "read_v2_config",
)
