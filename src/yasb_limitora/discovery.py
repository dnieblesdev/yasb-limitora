"""PRIVATE read-only YASB discovery and exact-name running-process probe (design §5).

Bounded and read-only: never parses `.env`/YAML/CSS, never creates directories or
files, and exposes no process-control API. Internal module: not exported from the
package ``__all__`` and not a public CLI surface.
"""
from __future__ import annotations

import ctypes
import ntpath
import os
import stat
from collections.abc import Callable, Iterable, Mapping
from typing import NamedTuple, Protocol

from .deadline import DeadlineContext

OUTCOME_DETECTED, OUTCOME_ABSENT, OUTCOME_INCONCLUSIVE = "detected", "absent", "inconclusive"
HOME_RESOLVED, HOME_UNSAFE, HOME_UNRESOLVED = "resolved", "unsafe", "unresolved"
ENV_PRESENT, ENV_ABSENT_CREATABLE, ENV_UNSAFE = "present", "absent-creatable", "unsafe-unreadable"
YASB_PROCESS_NAMES = frozenset({"yasb.exe", "yasb-limitora.exe"})
_REPARSE_ATTR = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
_MAX_UNINSTALL_SUBKEYS, _MAX_SNAPSHOT_ENTRIES, _TH32CS_SNAPPROCESS = 512, 8192, 0x2
_INVALID_HANDLE = ctypes.c_void_p(-1).value
_KNOWN_DIRS = (("LOCALAPPDATA", ("Programs", "yasb")), ("PROGRAMFILES", ("YASB",)), ("PROGRAMFILES(X86)", ("YASB",)))
SnapshotFn = Callable[[], Iterable[tuple[int, str]]]
ConfigHome = NamedTuple("ConfigHome", [("state", str), ("path", "str | None"), ("source", "str | None")])
RunningProbe = NamedTuple("RunningProbe", [("status", str), ("matches", "tuple[tuple[int, str], ...]")])
DiscoveryReport = NamedTuple("DiscoveryReport", [("outcome", str), ("install_evidence", "tuple[str, ...]"), ("config_home_state", str), ("config_home", "str | None"), ("env_file_state", "str | None"), ("process_status", str), ("reasons", "tuple[str, ...]")])

class SnapshotError(RuntimeError):
    """A sanitized fresh Win32 process-snapshot failure."""

class FsView(Protocol):
    """Metadata-only filesystem view contract; file contents are never opened."""
    def is_dir(self, path: str) -> bool: ...
    def is_reparse(self, path: str) -> bool: ...
    def file_kind(self, path: str) -> str: ...

class RealFs:
    """The real metadata-only filesystem view backed by os.lstat/os.path."""
    @staticmethod
    def is_dir(path: str) -> bool: return os.path.isdir(path)
    @staticmethod
    def is_reparse(path: str) -> bool:
        try: return bool(getattr(os.lstat(path), "st_file_attributes", 0) & _REPARSE_ATTR)
        except OSError: return False
    @staticmethod
    def file_kind(path: str) -> str:
        try: entry = os.lstat(path)
        except FileNotFoundError: return "missing"
        except OSError: return "unreadable"
        if getattr(entry, "st_file_attributes", 0) & _REPARSE_ATTR: return "unreadable"
        return "file" if stat.S_ISREG(entry.st_mode) else ("dir" if stat.S_ISDIR(entry.st_mode) else "unreadable")

REAL_FS = RealFs()

def _canonical_local_dir(value: object) -> str | None:
    """Return the canonical absolute local Windows directory form, or None when unsafe."""
    if not isinstance(value, str) or not value.strip(): return None
    text = value.replace("/", "\\")
    if text.startswith("\\"): return None  # UNC, \\.\ device, or \\?\ extended prefix
    drive, tail = ntpath.splitdrive(text)
    if len(drive) != 2 or drive[1] != ":" or not drive[0].isalpha() or not tail.startswith("\\"): return None
    parts = [part for part in tail.split("\\") if part]
    if not parts or ".." in tail.split("\\"): return None  # drive/root directory or traversal
    return drive + "\\" + "\\".join(parts)

def _components_safe(path: str, fs: FsView) -> bool:
    """Every existing component must be a directory and not a reparse point."""
    drive, tail = ntpath.splitdrive(path)
    prefix = drive + "\\"
    for part in [piece for piece in tail.split("\\") if piece]:
        prefix += part
        if fs.is_dir(prefix):
            if fs.is_reparse(prefix): return False
        elif fs.file_kind(prefix) != "missing": return False
        prefix += "\\"
    return True

def resolve_config_home(env: Mapping[str, str], *, fs: FsView = REAL_FS) -> ConfigHome:
    """Resolve the config home without reading `.env`; a present empty/unsafe
    `YASB_CONFIG_HOME` never falls back to a directory YASB did not select (§5.1)."""
    if "YASB_CONFIG_HOME" in env:
        canonical = _canonical_local_dir(env["YASB_CONFIG_HOME"])
        safe = canonical is not None and _components_safe(canonical, fs)
        return ConfigHome(HOME_RESOLVED if safe else HOME_UNSAFE, canonical if safe else None, "YASB_CONFIG_HOME")
    profile = _canonical_local_dir(env.get("USERPROFILE"))
    if profile is None or not _components_safe(profile, fs): return ConfigHome(HOME_UNRESOLVED, None, None)
    home = profile + "\\.config\\yasb"
    return ConfigHome(HOME_RESOLVED, home, "USERPROFILE") if _components_safe(home, fs) else ConfigHome(HOME_UNSAFE, None, "USERPROFILE")

def classify_env_file(home: str, *, fs: FsView = REAL_FS) -> str:
    """Classify the `.env` entry under `home` from metadata only; never opened."""
    kind = fs.file_kind(ntpath.join(home, ".env"))
    return ENV_PRESENT if kind == "file" else (ENV_ABSENT_CREATABLE if kind == "missing" else ENV_UNSAFE)

def scan_known_directories(env: Mapping[str, str], *, fs: FsView = REAL_FS) -> tuple[str, ...]:
    """Bounded probe 2: existence-only checks of the known YASB install directories."""
    hits = []
    for key, parts in _KNOWN_DIRS:
        candidate = ntpath.join(env[key], *parts) if env.get(key) else ""
        if candidate and fs.is_dir(candidate): hits.append("directory:" + candidate)
    return tuple(hits)

def scan_uninstall_registry() -> tuple[tuple[str, ...], bool]:
    """Bounded read-only probe 1: HKCU/HKLM uninstall display-name scan; (evidence, errored)."""
    try: import winreg
    except ImportError: return (), True
    hits: list[str] = []
    errored = False
    for hive, label in ((winreg.HKEY_CURRENT_USER, "HKCU"), (winreg.HKEY_LOCAL_MACHINE, "HKLM")):
        try:
            with winreg.OpenKey(hive, _UNINSTALL_KEY) as key:
                for index in range(min(winreg.QueryInfoKey(key)[0], _MAX_UNINSTALL_SUBKEYS)):
                    try:
                        with winreg.OpenKey(key, winreg.EnumKey(key, index)) as sub:
                            display = str(winreg.QueryValueEx(sub, "DisplayName")[0])
                            if "yasb" not in display.casefold(): continue
                            try: hits.append(f"registry:{label}:{display}@" + str(winreg.QueryValueEx(sub, "InstallLocation")[0]))
                            except OSError: hits.append(f"registry:{label}:{display}")
                    except OSError: continue
        except FileNotFoundError: continue  # a hive without uninstall entries is not a probe error
        except OSError: errored = True
    return tuple(hits), errored

class _ProcessEntry32W(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_uint32), ("cntUsage", ctypes.c_uint32), ("th32ProcessID", ctypes.c_uint32),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", ctypes.c_uint32), ("cntThreads", ctypes.c_uint32),
                ("th32ParentProcessID", ctypes.c_uint32), ("pcPriClassBase", ctypes.c_long), ("dwFlags", ctypes.c_uint32),
                ("szExeFile", ctypes.c_wchar * 260)]

def snapshot_processes() -> tuple[tuple[int, str], ...]:
    """Fresh bounded CreateToolhelp32Snapshot enumeration; opens no process handle."""
    if os.name != "nt": raise SnapshotError("unsupported_platform")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes, kernel32.CreateToolhelp32Snapshot.restype = [ctypes.c_uint32] * 2, ctypes.c_void_p
    kernel32.Process32FirstW.argtypes = kernel32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ProcessEntry32W)]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if not handle or handle == _INVALID_HANDLE: raise SnapshotError("snapshot_failed")
    try:
        entry = _ProcessEntry32W()
        entry.dwSize = ctypes.sizeof(_ProcessEntry32W)
        if not kernel32.Process32FirstW(handle, ctypes.byref(entry)): raise SnapshotError("snapshot_failed")
        entries: list[tuple[int, str]] = []
        while len(entries) < _MAX_SNAPSHOT_ENTRIES:
            entries.append((int(entry.th32ProcessID), str(entry.szExeFile)))
            if not kernel32.Process32NextW(handle, ctypes.byref(entry)): break
        return tuple(entries)
    finally:
        kernel32.CloseHandle(handle)

def probe_running_yasb(*, snapshot: SnapshotFn = snapshot_processes) -> RunningProbe:
    """Fresh exact-name probe (§5.2); snapshot failure is inconclusive, never clear."""
    try: entries = tuple(snapshot())
    except Exception: return RunningProbe("inconclusive", ())  # noqa: BLE001 - failure must not claim YASB is closed
    matches = tuple((pid, name) for pid, name in entries if str(name).casefold() in YASB_PROCESS_NAMES)
    return RunningProbe("running" if matches else "clear", matches)

def discover(env: Mapping[str, str] | None = None, *, fs: FsView = REAL_FS,
             registry: Callable[[], tuple[tuple[str, ...], bool]] = scan_uninstall_registry,
             snapshot: SnapshotFn = snapshot_processes, context: DeadlineContext | None = None) -> DiscoveryReport:
    """Bounded read-only discovery (§5.1): never creates state, never fails the install."""
    if context is not None and context.remaining_ns() <= 0:
        return DiscoveryReport(OUTCOME_INCONCLUSIVE, (), HOME_UNRESOLVED, None, None, "unknown", ("deadline-exhausted",))
    inherited = dict(os.environ) if env is None else dict(env)
    registry_hits, registry_errored = registry()
    probe = probe_running_yasb(snapshot=snapshot)
    evidence = tuple(registry_hits) + scan_known_directories(inherited, fs=fs) + tuple(f"process:{name}:{pid}" for pid, name in probe.matches)
    home = resolve_config_home(inherited, fs=fs)
    env_state = classify_env_file(home.path, fs=fs) if home.path is not None else None
    reasons = ["registry-probe-failed"] * registry_errored + ["process-snapshot-failed"] * (probe.status == "inconclusive")
    if reasons: outcome = OUTCOME_INCONCLUSIVE
    elif not evidence: outcome = OUTCOME_ABSENT
    elif home.state != HOME_RESOLVED: outcome, _ = OUTCOME_INCONCLUSIVE, reasons.append("config-home-" + home.state)
    elif env_state == ENV_UNSAFE: outcome, _ = OUTCOME_INCONCLUSIVE, reasons.append("env-file-unsafe-unreadable")
    else: outcome = OUTCOME_DETECTED
    return DiscoveryReport(outcome, evidence, home.state, home.path, env_state, probe.status, tuple(reasons))


# S04c: bounded adoption of the G2a-selected M6 mechanism (8.3 short-path alias).
# Read-only resolution only: no PATH lookup, no shell, no M3/M8 substitution, no YAML write.
# SP-no83 is nonfatal integration unavailability for the later installer: install proceeds,
# no command is written, and the machine class is reported unproven (design.md §6.3(a)-(d)).
INVOCATION_RESOLVED, INVOCATION_INVALID, INVOCATION_NO83 = "resolved", "invalid-input", "sp-no83"
MECHANISM_M6 = "M6"
CLASS_SF, CLASS_SP_83, CLASS_SP_NO83 = "SF", "SP-83", "SP-no83"
EXE_BASENAME = "yasb-limitora.exe"
ShortPathFn = Callable[[str], str | None]
IdentityFn = Callable[[str], object]
class InvocationResolution(NamedTuple):
    state: str
    command: str | None
    machine_class: str | None
    mechanism: str | None
    use_shell: bool
    reason: str | None


def get_short_path_name(path: str) -> str | None:
    if os.name != "nt":
        return None
    try:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        kernel.GetShortPathNameW.restype = ctypes.c_uint32
        buffer = ctypes.create_unicode_buffer(512)
        length = kernel.GetShortPathNameW(path, buffer, len(buffer))
    except OSError:
        return None
    return buffer.value if 0 < length < len(buffer) else None


def file_identity(path: str) -> tuple[int, int] | None:
    try:
        entry = os.lstat(path)
    except OSError:
        return None
    return (entry.st_dev, entry.st_ino)


def _invocation_invalid(reason: str) -> InvocationResolution:
    return InvocationResolution(INVOCATION_INVALID, None, None, None, False, reason)


def _invocation_no83(reason: str) -> InvocationResolution:
    return InvocationResolution(INVOCATION_NO83, None, CLASS_SP_NO83, MECHANISM_M6, False, reason)


def _is_canonical_spelling(path: str) -> bool:
    """True only when path equals its own canonical local Windows lexical spelling."""
    if "/" in path:
        return False
    drive, tail = ntpath.splitdrive(path)
    if len(drive) != 2 or drive[1] != ":" or not drive[0].isalpha() or not tail.startswith("\\"):
        return False
    return all(part not in {"", ".", ".."} for part in tail[1:].split("\\"))


def _components_dirs(path: str, fs: FsView) -> bool:
    """Strict invocation-only variant: every ancestor below the drive root must
    exist as a safe dir (is_dir and not is_reparse); missing is never tolerated."""
    drive, tail = ntpath.splitdrive(path)
    prefix = drive + "\\"
    for part in filter(None, tail.split("\\")):
        prefix += part
        if not (fs.is_dir(prefix) and not fs.is_reparse(prefix)):
            return False
        prefix += "\\"
    return True


def resolve_installed_invocation(exe_path: str, *, expected_basename: str = EXE_BASENAME,
                                 fs: FsView = REAL_FS, short_path: ShortPathFn = get_short_path_name,
                                 identity: IdentityFn = file_identity) -> InvocationResolution:
    basename = ntpath.basename(exe_path)
    parent = ntpath.dirname(exe_path)
    if not _is_canonical_spelling(exe_path) or _canonical_local_dir(parent) is None or not _components_dirs(parent, fs):
        return _invocation_invalid("path-unsafe")
    if basename.casefold() != expected_basename.casefold():
        return _invocation_invalid("basename-mismatch")
    kind = fs.file_kind(exe_path)
    if kind == "missing":
        return _invocation_invalid("exe-missing")
    if kind != "file":
        return _invocation_invalid("exe-unsafe")
    if " " not in exe_path:
        return InvocationResolution(INVOCATION_RESOLVED, exe_path, CLASS_SF, MECHANISM_M6, False, None)
    try:
        alias = short_path(exe_path)
    except Exception:  # noqa: BLE001 - any short-path failure must fail closed, never fall back
        alias = None
    if not alias:
        return _invocation_no83("short-name-unavailable")
    if " " in alias:
        return _invocation_no83("alias-contains-space")
    alias_parent = ntpath.dirname(alias)
    if not _is_canonical_spelling(alias) or _canonical_local_dir(alias_parent) is None or not _components_dirs(alias_parent, fs):
        return _invocation_no83("alias-unsafe")
    if fs.file_kind(alias) != "file":
        return _invocation_no83("alias-unsafe")
    target = identity(exe_path)
    if target is None or identity(alias) != target:
        return _invocation_no83("alias-identity-mismatch")
    return InvocationResolution(INVOCATION_RESOLVED, alias, CLASS_SP_83, MECHANISM_M6, False, None)
