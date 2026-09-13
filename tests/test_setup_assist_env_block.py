"""S06: consented byte-preserving YASB .env block assistance."""
from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest  # pyright: ignore[reportMissingImports]

env = importlib.import_module("yasb_limitora._env_block")


def apply(tmp_path: Path, contents: bytes | None, **kwargs):
    home, state = tmp_path / "yasb", tmp_path / "state"
    home.mkdir()
    target = home / ".env"
    if contents is not None:
        target.write_bytes(contents)
    return env.apply(home, state, r"C:\PROGRA~1\yasb-limitora.exe", **kwargs), target, state


def test_requires_explicit_consent_without_creating_target(tmp_path):
    result, target, state = apply(tmp_path, None, consent=False)
    assert result.reason == "env-consent-required" and not target.exists() and not state.exists()


def test_creates_only_commented_m6_block_after_consent(tmp_path):
    result, target, state = apply(tmp_path, None)
    text = target.read_text(encoding="utf-8")
    assert result.reason is None and text.count(env.START) == text.count(env.END) == 1
    assert all(line.startswith("#") for line in text.splitlines())
    assert "PROGRA~1" in text and (state / "backups").is_dir() is False


def test_preserves_unrelated_bytes_idempotently_bom_and_dominant_crlf(tmp_path):
    original = b"\xef\xbb\xbfUSER=unchanged\r\n# keep\r\n"
    first, target, state = apply(tmp_path, original)
    once = target.read_bytes()
    second = env.apply(target.parent, state, r"C:\PROGRA~1\yasb-limitora.exe")
    final = target.read_bytes()
    assert first.reason is second.reason is None and final == once
    assert final.startswith(b"\xef\xbb\xbfUSER=unchanged\r\n# keep\r\n")
    assert b"\n" not in final.replace(b"\r\n", b"")
    assert (state / "backups").glob("env.*.bak")


@pytest.mark.parametrize(
    "contents,reason",
    [
        (b"# >>> yasb-limitora managed block v1 (id: yasb-limitora) >>>\n" * 2, "env-markers-invalid"),
        (b"# >>> yasb-limitora managed block v1 (id: yasb-limitora) >>>\n", "env-markers-invalid"),
        (b"\xff", "env-undecodable"),
    ],
)
def test_invalid_existing_content_refuses_byte_identically(tmp_path, contents, reason):
    result, target, _state = apply(tmp_path, contents)
    assert result.reason == reason and target.read_bytes() == contents


def test_refuses_unsafe_home_target_and_credential_like_rendered_content(tmp_path, monkeypatch):
    home, state = tmp_path / "home", tmp_path / "state"
    home.mkdir()
    monkeypatch.setattr(env, "_safe", lambda _path: False)
    assert env.apply(home, state, "C:\\ok.exe").reason == "env-home-unsafe"
    monkeypatch.setattr(env, "_safe", lambda _path: True)
    (home / ".env").mkdir()
    assert env.apply(home, state, "C:\\ok.exe").reason == "env-target-unsafe"
    (home / ".env").rmdir()
    assert env.apply(home, state, "C:\\token.exe").reason == "env-rendered-credential"


def test_replace_failure_restores_backup_and_restore_failure_is_reported(tmp_path, monkeypatch):
    original = b"USER=unchanged\n"
    result, target, state = apply(tmp_path, original)
    assert result.reason is None
    target.write_bytes(original)
    real_replace, calls = os.replace, []
    def fail_replace(source, destination):
        calls.append((source, destination))
        if len(calls) == 1:
            raise OSError("replace")
        return real_replace(source, destination)
    monkeypatch.setattr(env.os, "replace", fail_replace)
    result = env.apply(target.parent, state, "C:\\PROGRA~1\\yasb-limitora.exe")
    assert result.reason == "env-replace-failed" and target.read_bytes() == original
    monkeypatch.setattr(env.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("no restore")))
    result = env.apply(target.parent, state, "C:\\PROGRA~1\\yasb-limitora.exe")
    assert result.reason == "env-rollback-failed"


def test_create_failure_leaves_absent_target(tmp_path, monkeypatch):
    home, state = tmp_path / "home", tmp_path / "state"
    home.mkdir()
    monkeypatch.setattr(env.tempfile, "mkstemp", lambda **_kwargs: (_ for _ in ()).throw(OSError("create")))
    result = env.apply(home, state, "C:\\PROGRA~1\\yasb-limitora.exe")
    assert result.reason == "env-create-failed" and not (home / ".env").exists()


def test_verification_failure_rolls_back_created_file(tmp_path, monkeypatch):
    home, state = tmp_path / "home", tmp_path / "state"
    home.mkdir()
    original_read = Path.read_bytes
    def wrong_read(self):
        return b"wrong" if self.name == ".env" else original_read(self)
    monkeypatch.setattr(Path, "read_bytes", wrong_read)
    result = env.apply(home, state, "C:\\PROGRA~1\\yasb-limitora.exe")
    assert result.reason == "env-verify-failed" and not (home / ".env").exists()
