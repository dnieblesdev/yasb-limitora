"""Private, consented, byte-preserving YASB ``.env`` managed-block transaction."""
from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from contextlib import suppress
from pathlib import Path
from typing import NamedTuple

from .config import _CREDENTIAL_KEY

START = "# >>> yasb-limitora managed block v1 (id: yasb-limitora) >>>"
END = "# <<< yasb-limitora managed block v1 (id: yasb-limitora) <<<"


class Result(NamedTuple):
    reason: str | None


def _safe(path: Path) -> bool:
    """Reject a target or any existing ancestor that is a reparse/symlink point."""
    try:
        current = path
        while True:
            if current.exists() and current.is_symlink():
                return False
            if current.parent == current:
                return True
            current = current.parent
    except OSError:
        return False


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


def apply(home: Path, state_root: Path, invocation: str, *, consent: bool = True) -> Result:
    """Apply exactly one comment-only block; every refusal leaves YASB bytes untouched."""
    if not consent:
        return Result("env-consent-required")
    target = home / ".env"
    if not _safe(home):
        return Result("env-home-unsafe")
    if target.exists() and (target.is_symlink() or not target.is_file()):
        return Result("env-target-unsafe")
    created_home, existed = not home.exists(), target.exists()
    try:
        if created_home:
            home.mkdir(parents=True)
        raw = target.read_bytes() if existed else b""
    except OSError:
        return Result("env-target-unsafe")
    replacement, reason = _rewrite(raw, invocation)
    if reason:
        return Result(reason)
    backup: Path | None = None
    temporary: str | None = None
    try:
        if existed:
            backups = state_root / "backups"
            backups.mkdir(parents=True, exist_ok=True)
            backup = backups / ("env." + uuid.uuid4().hex + ".bak")
            shutil.copyfile(target, backup)
        fd, temporary = tempfile.mkstemp(prefix=".env.yasb-limitora.tmp-", dir=home)
        with os.fdopen(fd, "wb") as stream:
            stream.write(replacement or b"")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        if target.read_bytes() != replacement:
            raise RuntimeError("verify")
        return Result(None)
    except RuntimeError:
        reason = "env-verify-failed"
    except OSError:
        reason = _failure_reason(existed)
    finally:
        if temporary is not None:
            with suppress(OSError):
                os.unlink(temporary)
    try:
        if backup is not None:
            os.replace(backup, target)
        elif target.exists():
            target.unlink()
        if created_home and not any(home.iterdir()):
            home.rmdir()
    except OSError:
        return Result("env-rollback-failed")
    return Result(reason)
