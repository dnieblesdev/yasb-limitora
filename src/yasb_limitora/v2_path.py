"""Lexical, lookup-free path contracts used by JSON v2."""

from __future__ import annotations

import ctypes
import ntpath
import os


MAX_PATH_UTF16_UNITS = 32_767


class V2PathError(ValueError):
    """Raised when a v2 path is outside the safe local-path contract."""


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
    if ntpath.splitdrive(value)[0] or value.startswith(("\\", "/")):
        return ntpath.normpath(value.replace("/", "\\"))
    return os.path.normpath(os.path.abspath(value))


def canonicalize_v2_path(path: object) -> str:
    """Return a normalized effective path without checking the filesystem."""

    if not isinstance(path, str) or not path:
        raise V2PathError("invalid path")
    lexical = path.replace("/", "\\")
    if lexical.startswith(("\\\\?\\", "\\\\.\\", "\\\\")):
        raise V2PathError("non-local path")
    canonical = _lexical_full_path(lexical)
    if len(canonical.encode("utf-16-le")) // 2 > MAX_PATH_UTF16_UNITS:
        raise V2PathError("path is too long")
    return canonical


def path_identity(path: object) -> str:
    """Return the opaque-independent case-insensitive lexical identity."""

    return canonicalize_v2_path(path).casefold()


__all__ = ("MAX_PATH_UTF16_UNITS", "V2PathError", "canonicalize_v2_path", "path_identity")
