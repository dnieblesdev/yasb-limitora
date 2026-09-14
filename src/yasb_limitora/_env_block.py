"""Private, consented, byte-preserving YASB ``.env`` managed-block transaction."""
from __future__ import annotations

import ctypes
import os
import stat
import tempfile
import uuid
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import NamedTuple

from .config import _CREDENTIAL_KEY

START = "# >>> yasb-limitora managed block v1 (id: yasb-limitora) >>>"
END = "# <<< yasb-limitora managed block v1 (id: yasb-limitora) <<<"


class Result(NamedTuple):
    reason: str | None


def _reparse(path: Path) -> bool:
    """Windows junctions are reparse points but are not necessarily symlinks."""
    try:
        return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except FileNotFoundError:
        return False
    except OSError:
        return True


def _safe(path: Path) -> bool:
    """Reject every existing reparse component, including a junction or leaf."""
    try:
        current = path
        while True:
            if _reparse(current):
                return False
            if current.parent == current:
                return True
            current = current.parent
    except OSError:
        return False


def _raw_handle_final_path(handle: int) -> str | None:
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = ctypes.WinDLL("kernel32", use_last_error=True).GetFinalPathNameByHandleW(
            ctypes.c_void_p(handle), buffer, len(buffer), 0
        )
        return buffer.value if 0 < length < len(buffer) else None
    except OSError:
        return None


def _handle_final_path(fd: int) -> str | None:
    if os.name != "nt":
        return str(Path(os.readlink(f"/proc/self/fd/{fd}"))) if os.path.exists(f"/proc/self/fd/{fd}") else None
    try:
        import msvcrt
        return _raw_handle_final_path(msvcrt.get_osfhandle(fd))
    except (ImportError, OSError, ValueError):
        return None


def _final_matches(final: str | None, path: Path) -> bool:
    return final is not None and final.casefold() == ("\\\\?\\" + str(path.absolute())).casefold()


def _opened_at(fd: int, path: Path) -> bool:
    return _final_matches(_handle_final_path(fd), path)


@contextmanager
def _held_destination_directory(path: Path):
    """Keep the verified Windows destination directory unrenamable through replace/rollback."""
    if not _safe(path) or not path.is_dir():
        raise OSError("unsafe destination directory")
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        try:
            if not _opened_at(fd, path):
                raise OSError("unsafe destination directory")
            yield
        finally:
            os.close(fd)
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.restype = ctypes.c_void_p
    handle = create_file(str(path), 0x80000000, 0x3, None, 3, 0x02000000, None)
    if handle == ctypes.c_void_p(-1).value or not _final_matches(_raw_handle_final_path(handle), path):
        if handle != ctypes.c_void_p(-1).value:
            kernel32.CloseHandle(ctypes.c_void_p(handle))
        raise OSError("unsafe destination directory")
    try:
        yield
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(handle))


def _checked_read(path: Path) -> bytes:
    if not _safe(path) or not path.is_file():
        raise OSError("unsafe read")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    try:
        if not _opened_at(fd, path):
            raise OSError("unsafe read")
        with os.fdopen(fd, "rb") as stream:
            return stream.read()
    except BaseException:
        with suppress(OSError):
            os.close(fd)
        raise


def _restore(backup: Path, target: Path) -> None:
    """Restore through a verified target handle; never rename backup bytes by pathname."""
    raw = _checked_read(backup)
    fd = os.open(target, os.O_WRONLY | getattr(os, "O_BINARY", 0))
    try:
        if not _opened_at(fd, target):
            raise OSError("unsafe rollback")
        os.ftruncate(fd, 0)
        os.write(fd, raw)
        os.fsync(fd)
    finally:
        os.close(fd)
    if _checked_read(target) != raw:
        raise OSError("rollback verify")


def _checked_backup(backups: Path, raw: bytes) -> Path:
    if not _safe(backups.parent):
        raise OSError("unsafe state")
    backups.mkdir(parents=True, exist_ok=True)
    if not _safe(backups) or not backups.is_dir():
        raise OSError("unsafe state")
    backup = backups / ("env." + uuid.uuid4().hex + ".bak")
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    try:
        if not _safe(backup) or not _opened_at(fd, backup):
            raise OSError("unsafe backup")
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        return backup
    except BaseException:
        with suppress(OSError):
            os.close(fd)
        with suppress(OSError):
            backup.unlink()
        raise


def _render(invocation: str, newline: str) -> bytes | None:
    lines = (
        START,
        "# Managed by yasb-limitora setup. YASB loads this file at startup.",
        "# This block is documentation only: every line is a comment.",
        "# Private values remain in your own .env entries.",
        "# Default configuration location: %LOCALAPPDATA%\\yasb-limitora\\config.json",
        "# M6 no-PATH invocation (short-path alias): " + invocation,
        END,
    )
    text = newline.join(lines) + newline
    return None if _CREDENTIAL_KEY.search(text) else text.encode("utf-8")


def _failure_reason(existed: bool) -> str:
    return "env-replace-failed" if existed else "env-create-failed"


def _rewrite(raw: bytes, invocation: str) -> tuple[bytes | None, str | None]:
    bom, content = (b"\xef\xbb\xbf", raw[3:]) if raw.startswith(b"\xef\xbb\xbf") else (b"", raw)
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return None, "env-undecodable"
    newline = "\r\n" if content.count(b"\r\n") >= content.count(b"\n") - content.count(b"\r\n") else "\n"
    rendered = _render(invocation, newline)
    if rendered is None:
        return None, "env-rendered-credential"
    lines = text.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == START]
    ends = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == END]
    if len(starts) != len(ends) or len(starts) > 1 or (starts and starts[0] >= ends[0]):
        return None, "env-markers-invalid"
    if starts:
        output = "".join(lines[:starts[0]]).encode() + rendered + "".join(lines[ends[0] + 1:]).encode()
    else:
        output = content + (b"" if not content or content.endswith((b"\n", b"\r")) else newline.encode()) + rendered
    return bom + output, None


def apply(home: Path, state_root: Path, invocation: str, *, consent: bool = False) -> Result:
    """Apply one comment-only block, rechecking every mutable pathname boundary."""
    if not isinstance(consent, bool) or not consent:
        return Result("env-consent-required")
    target, backups = home / ".env", state_root / "backups"
    if not _safe(home):
        return Result("env-home-unsafe")
    if not _safe(state_root):
        return Result("env-state-unsafe")
    if target.exists() and (not _safe(target) or not target.is_file()):
        return Result("env-target-unsafe")
    created_home, existed = not home.exists(), target.exists()
    try:
        if created_home:
            home.mkdir(parents=True)
        if not _safe(home):
            return Result("env-home-unsafe")
        raw = _checked_read(target) if existed else b""
    except OSError:
        return Result("env-target-unsafe")
    replacement, reason = _rewrite(raw, invocation)
    if reason:
        return Result(reason)
    backup: Path | None = None
    temporary: str | None = None
    try:
        if existed:
            backup = _checked_backup(backups, raw)
        if not _safe(home) or not _safe(state_root):
            raise OSError("unsafe temp parent")
        with _held_destination_directory(home):
            try:
                fd, temporary = tempfile.mkstemp(prefix=".env.yasb-limitora.tmp-", dir=home)
                with os.fdopen(fd, "wb") as stream:
                    if not _safe(Path(temporary)) or not _opened_at(fd, Path(temporary)):
                        raise OSError("unsafe temp")
                    stream.write(replacement or b"")
                    stream.flush()
                    os.fsync(stream.fileno())
                if not _safe(home) or not _safe(target) or not _safe(state_root):
                    raise OSError("unsafe replace")
                os.replace(temporary, target)
                if _checked_read(target) != replacement:
                    raise RuntimeError("verify")
                return Result(None)
            except RuntimeError:
                reason = "env-verify-failed"
            except OSError:
                reason = _failure_reason(existed)
            try:
                if not _safe(home) or not _safe(state_root) or (backup is not None and not _safe(backup)):
                    raise OSError("unsafe rollback")
                if backup is not None:
                    _restore(backup, target)
                elif target.exists() and _safe(target):
                    target.unlink()
                if created_home and _safe(home) and not any(home.iterdir()):
                    home.rmdir()
            except OSError:
                return Result("env-rollback-failed")
            return Result(reason)
    except OSError:
        return Result(_failure_reason(existed))
    finally:
        if temporary is not None:
            with suppress(OSError):
                Path(temporary).unlink()
