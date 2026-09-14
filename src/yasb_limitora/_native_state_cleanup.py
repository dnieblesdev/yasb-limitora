"""Windows handle-bound, no-follow deletion for the literal state directory."""
from __future__ import annotations

import ctypes
import os
import struct
from ctypes import wintypes

_DELETE, _SYNC, _READ_ATTRS, _LIST = 0x10000, 0x100000, 0x80, 1
_SHARE, _OPEN, _DIR, _FILE, _REPARSE, _SYNC_IO = 7, 1, 1, 0x40, 0x200000, 0x20
_INVALID, _ATTR_REPARSE, _NO_MORE = wintypes.HANDLE(-1).value, 0x400, -2147483642


class _US(ctypes.Structure):
    _fields_ = [("Length", wintypes.USHORT), ("MaximumLength", wintypes.USHORT), ("Buffer", wintypes.LPWSTR)]


class _OA(ctypes.Structure):
    _fields_ = [("Length", wintypes.ULONG), ("RootDirectory", wintypes.HANDLE), ("ObjectName", ctypes.POINTER(_US)), ("Attributes", wintypes.ULONG), ("SecurityDescriptor", wintypes.LPVOID), ("SecurityQualityOfService", wintypes.LPVOID)]


class _IOSB(ctypes.Structure):
    _fields_ = [("Status", ctypes.c_long), ("Information", ctypes.c_size_t)]


class _INFO(ctypes.Structure):
    _fields_ = [("Attributes", wintypes.DWORD), ("Creation", wintypes.FILETIME), ("Access", wintypes.FILETIME), ("Write", wintypes.FILETIME), ("Volume", wintypes.DWORD), ("SizeHigh", wintypes.DWORD), ("SizeLow", wintypes.DWORD), ("Links", wintypes.DWORD), ("IndexHigh", wintypes.DWORD), ("IndexLow", wintypes.DWORD)]


def _api():
    if os.name != "nt":
        return None
    kernel, ntdll = ctypes.WinDLL("kernel32", use_last_error=True), ctypes.WinDLL("ntdll")
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(_INFO)]
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    kernel.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, wintypes.INT, wintypes.LPVOID, wintypes.DWORD]
    kernel.SetFileInformationByHandle.restype = wintypes.BOOL
    ntdll.NtCreateFile.argtypes = [ctypes.POINTER(wintypes.HANDLE), wintypes.ULONG, ctypes.POINTER(_OA), ctypes.POINTER(_IOSB), wintypes.LPVOID, wintypes.ULONG, wintypes.ULONG, wintypes.ULONG, wintypes.ULONG, wintypes.LPVOID, wintypes.ULONG]
    ntdll.NtCreateFile.restype = ctypes.c_long
    ntdll.NtQueryDirectoryFile.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.LPVOID, wintypes.LPVOID, ctypes.POINTER(_IOSB), wintypes.LPVOID, wintypes.ULONG, wintypes.ULONG, wintypes.BOOL, wintypes.LPVOID, wintypes.BOOL]
    ntdll.NtQueryDirectoryFile.restype = ctypes.c_long
    return kernel, ntdll


def _close(handle):
    _api()[0].CloseHandle(handle)


def _checked(handle):
    api = _api()
    if not api or not handle or handle == _INVALID:
        raise OSError("open failed")
    info = _INFO()
    if not api[0].GetFileInformationByHandle(handle, ctypes.byref(info)) or info.Attributes & _ATTR_REPARSE:
        _close(handle)
        raise OSError("reparse")
    return handle, (info.IndexHigh, info.IndexLow, info.Attributes)


def _final(handle):
    kernel = _api()[0]
    length = kernel.GetFinalPathNameByHandleW(handle, None, 0, 0)
    if not length:
        raise OSError("final path failed")
    value = ctypes.create_unicode_buffer(length + 1)
    if not kernel.GetFinalPathNameByHandleW(handle, value, len(value), 0):
        raise OSError("final path failed")
    return os.path.normcase(value.value.removeprefix("\\\\?\\"))


def _open_parent(path):
    api = _api()
    handle = api[0].CreateFileW(path, _SYNC | _READ_ATTRS | _LIST, _SHARE, None, 3, 0x2000000 | _REPARSE, None)
    return _checked(handle)[0]


def _identity(handle):
    return _checked(handle)[1]


def _open_relative(parent, name, directory):
    api = _api()
    value = ctypes.create_unicode_buffer(name)
    us = _US(len(name) * 2, (len(name) + 1) * 2, ctypes.cast(value, wintypes.LPWSTR))
    oa, iosb, handle = _OA(ctypes.sizeof(_OA), parent, ctypes.pointer(us), 0, None, None), _IOSB(), wintypes.HANDLE()
    options = (_DIR if directory else _FILE) | _REPARSE | _SYNC_IO
    status = api[1].NtCreateFile(ctypes.byref(handle), _DELETE | _SYNC | _READ_ATTRS | (_LIST if directory else 0), ctypes.byref(oa), ctypes.byref(iosb), None, 0, _SHARE, _OPEN, options, None, 0)
    if status < 0:
        raise OSError("relative open failed")
    return _checked(handle)[0]


def _names(handle):
    api, first, buffer = _api(), True, ctypes.create_string_buffer(32768)
    while True:
        iosb = _IOSB()
        status = api[1].NtQueryDirectoryFile(handle, None, None, None, ctypes.byref(iosb), buffer, len(buffer), 1, False, None, first)
        first = False
        if status == _NO_MORE:
            return
        if status < 0:
            raise OSError("enumeration failed")
        offset = 0
        while True:
            next_offset, attrs, length = struct.unpack_from("<I", buffer, offset)[0], struct.unpack_from("<I", buffer, offset + 56)[0], struct.unpack_from("<I", buffer, offset + 60)[0]
            name = ctypes.string_at(ctypes.addressof(buffer) + offset + 64, length).decode("utf-16-le")
            if name not in {".", ".."}:
                if attrs & _ATTR_REPARSE or "\\" in name or "/" in name:
                    raise OSError("reparse")
                yield name, bool(attrs & 0x10)
            if not next_offset:
                break
            offset += next_offset


def _delete(handle):
    delete = wintypes.BOOL(True)
    if not _api()[0].SetFileInformationByHandle(handle, 4, ctypes.byref(delete), ctypes.sizeof(delete)):
        raise OSError("delete failed")


def _tree(handle):
    for name, directory in _names(handle):
        child = _open_relative(handle, name, directory)
        try:
            if directory:
                _tree(child)
            _delete(child)
        finally:
            _close(child)


def delete_directory(path: str) -> bool:
    """Delete only this opened directory tree; unavailable native support refuses."""
    if not _api() or not os.path.isabs(path):
        return False
    parent_path, name = os.path.dirname(path), os.path.basename(path)
    if not name:
        return False
    parent = root = None
    try:
        parent = _open_parent(parent_path)
        root = _open_relative(parent, name, True)
        if _final(root) != os.path.normcase(os.path.abspath(path)):
            raise OSError("root final path mismatch")
        probe = _open_relative(parent, name, True)
        try:
            if _identity(probe) != _identity(root):
                raise OSError("root swapped")
        finally:
            _close(probe)
        _tree(root)
        _delete(root)
        return True
    except OSError:
        return False
    finally:
        if root:
            _close(root)
        if parent:
            _close(parent)
