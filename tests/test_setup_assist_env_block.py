"""S06: consented byte-preserving YASB .env block assistance."""
from __future__ import annotations

import importlib
import os
import shutil
import subprocess
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


def test_direct_mutation_defaults_to_fail_closed_consent(tmp_path):
    result, target, state = apply(tmp_path, None)
    assert result.reason == "env-consent-required" and not target.exists() and not state.exists()


def test_creates_only_commented_m6_block_after_consent(tmp_path):
    result, target, state = apply(tmp_path, None, consent=True)
    text = target.read_text(encoding="utf-8")
    assert result.reason is None and text.count(env.START) == text.count(env.END) == 1
    assert all(line.startswith("#") for line in text.splitlines())
    assert "PROGRA~1" in text and (state / "backups").is_dir() is False


def test_preserves_unrelated_bytes_idempotently_bom_and_dominant_crlf(tmp_path):
    original = b"\xef\xbb\xbfUSER=unchanged\r\n# keep\r\n"
    first, target, state = apply(tmp_path, original, consent=True)
    once = target.read_bytes()
    second = env.apply(target.parent, state, r"C:\PROGRA~1\yasb-limitora.exe", consent=True)
    final = target.read_bytes()
    assert first.reason is second.reason is None and final == once
    assert final.startswith(b"\xef\xbb\xbfUSER=unchanged\r\n# keep\r\n")
    assert b"\n" not in final.replace(b"\r\n", b"")
    backups = list((state / "backups").glob("env.*.bak"))
    assert len(backups) == 2 and original in {backup.read_bytes() for backup in backups}


@pytest.mark.parametrize(
    "contents,reason",
    [
        (b"# >>> yasb-limitora managed block v1 (id: yasb-limitora) >>>\n" * 2, "env-markers-invalid"),
        (b"# >>> yasb-limitora managed block v1 (id: yasb-limitora) >>>\n", "env-markers-invalid"),
        (b"\xff", "env-undecodable"),
    ],
)
def test_invalid_existing_content_refuses_byte_identically(tmp_path, contents, reason):
    result, target, _state = apply(tmp_path, contents, consent=True)
    assert result.reason == reason and target.read_bytes() == contents


def test_refuses_unsafe_home_target_and_credential_like_rendered_content(tmp_path, monkeypatch):
    home, state = tmp_path / "home", tmp_path / "state"
    home.mkdir()
    monkeypatch.setattr(env, "_safe", lambda _path: False)
    assert env.apply(home, state, "C:\\ok.exe", consent=True).reason == "env-home-unsafe"
    monkeypatch.setattr(env, "_safe", lambda _path: True)
    (home / ".env").mkdir()
    assert env.apply(home, state, "C:\\ok.exe", consent=True).reason == "env-target-unsafe"
    (home / ".env").rmdir()
    assert env.apply(home, state, "C:\\token.exe", consent=True).reason == "env-rendered-credential"


def test_replace_failure_restores_backup_and_restore_failure_is_reported(tmp_path, monkeypatch):
    original = b"USER=unchanged\n"
    result, target, state = apply(tmp_path, original, consent=True)
    assert result.reason is None
    target.write_bytes(original)
    real_replace, calls = os.replace, []
    def fail_replace(source, destination):
        calls.append((source, destination))
        if len(calls) == 1:
            raise OSError("replace")
        return real_replace(source, destination)
    monkeypatch.setattr(env.os, "replace", fail_replace)
    result = env.apply(target.parent, state, "C:\\PROGRA~1\\yasb-limitora.exe", consent=True)
    assert result.reason == "env-replace-failed" and target.read_bytes() == original
    monkeypatch.setattr(env.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("replace")))
    monkeypatch.setattr(env, "_restore", lambda *_: (_ for _ in ()).throw(OSError("no restore")))
    result = env.apply(target.parent, state, "C:\\PROGRA~1\\yasb-limitora.exe", consent=True)
    assert result.reason == "env-rollback-failed"


def test_create_failure_leaves_absent_target(tmp_path, monkeypatch):
    home, state = tmp_path / "home", tmp_path / "state"
    home.mkdir()
    monkeypatch.setattr(env.tempfile, "mkstemp", lambda **_kwargs: (_ for _ in ()).throw(OSError("create")))
    result = env.apply(home, state, "C:\\PROGRA~1\\yasb-limitora.exe", consent=True)
    assert result.reason == "env-create-failed" and not (home / ".env").exists()


def test_verification_failure_rolls_back_created_file(tmp_path, monkeypatch):
    home, state = tmp_path / "home", tmp_path / "state"
    home.mkdir()
    monkeypatch.setattr(env, "_checked_read", lambda _path: b"wrong")
    result = env.apply(home, state, "C:\\PROGRA~1\\yasb-limitora.exe", consent=True)
    assert result.reason == "env-verify-failed" and not (home / ".env").exists()


def _junction(link: Path, target: Path) -> None:
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)


@pytest.mark.skipif(os.name != "nt", reason="Windows reparse proof")
def test_opened_handle_rejects_home_swap_at_read_boundary(tmp_path, monkeypatch):
    home, held, outside = tmp_path / "home", tmp_path / "held", tmp_path / "outside"
    home.mkdir()
    outside.mkdir()
    target = home / ".env"
    target.write_bytes(b"ORIGINAL")
    real_open = env.os.open
    def swapped_open(path, *args):
        fd = real_open(path, *args)
        if Path(path) == target:
            home.rename(held)
            _junction(home, outside)
        return fd
    monkeypatch.setattr(env.os, "open", swapped_open)
    with pytest.raises(OSError):
        env._checked_read(target)
    assert not list(outside.iterdir())
    shutil.rmtree(tmp_path, ignore_errors=True)


@pytest.mark.skipif(os.name != "nt", reason="Windows reparse proof")
def test_rollback_swap_at_replace_boundary_never_leaks_original_bytes(tmp_path, monkeypatch):
    original = b"USER=original\n"
    result, target, state = apply(tmp_path, original, consent=True)
    assert result.reason is None
    target.write_bytes(original)
    home, held, outside = target.parent, target.parent.with_name("held"), tmp_path / "outside"
    outside.mkdir()
    real_replace, calls = env.os.replace, []
    def raced_replace(source, destination):
        calls.append((source, destination))
        if len(calls) == 1:
            raise OSError("replace")
        return real_replace(source, destination)
    monkeypatch.setattr(env.os, "replace", raced_replace)
    restore = env._restore
    def raced_restore(backup, destination):
        home.rename(held)
        _junction(home, outside)
        return restore(backup, destination)
    monkeypatch.setattr(env, "_restore", raced_restore)
    result = env.apply(home, state, r"C:\PROGRA~1\yasb-limitora.exe", consent=True)
    assert result.reason == "env-rollback-failed" and not (outside / ".env").exists()
    shutil.rmtree(tmp_path, ignore_errors=True)


@pytest.mark.skipif(os.name != "nt", reason="Windows reparse proof")
@pytest.mark.parametrize("unsafe", ("home", "target", "state"))
def test_real_windows_junctions_refuse_without_writing(tmp_path, unsafe):
    home, state, outside = tmp_path / "home", tmp_path / "state", tmp_path / "outside"
    outside.mkdir()
    if unsafe == "home":
        _junction(home, outside)
    else:
        home.mkdir()
        if unsafe == "target":
            _junction(home / ".env", outside)
        else:
            _junction(state, outside)
    result = env.apply(home, state, r"C:\PROGRA~1\yasb-limitora.exe", consent=True)
    assert result.reason in {"env-home-unsafe", "env-target-unsafe", "env-state-unsafe"}
    assert not (outside / ".env").exists() and not list(outside.iterdir())
