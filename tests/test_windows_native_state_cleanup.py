"""Direct native no-follow state-tree deletion proof; temp roots only."""
from __future__ import annotations

import importlib
import os
import subprocess
from pathlib import Path

import pytest

native = importlib.import_module("yasb_limitora._native_state_cleanup")
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows native API required")


def _junction(link: Path, target: Path) -> None:
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, check=False, text=True)
    if result.returncode:
        pytest.skip("junction creation unavailable")


def test_normal_nested_delete_and_handles_close(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "state"
    (root / "one" / "two").mkdir(parents=True)
    (root / "one" / "two" / "cache").write_text("x")
    opened: list[int] = []
    closed: list[int] = []
    original_close, original_parent, original_relative = native._close, native._open_parent, native._open_relative
    monkeypatch.setattr(native, "_open_parent", lambda path: (opened.append(handle := original_parent(path)), handle)[1])
    monkeypatch.setattr(native, "_open_relative", lambda parent, name, directory: (opened.append(handle := original_relative(parent, name, directory)), handle)[1])
    monkeypatch.setattr(native, "_close", lambda handle: (closed.append(handle), original_close(handle))[1])
    assert native.delete_directory(str(root))
    def value(handle):
        return handle.value if hasattr(handle, "value") else handle
    assert not root.exists() and sorted(map(value, opened)) == sorted(map(value, closed))


def test_exceptional_nested_delete_closes_every_open_handle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "state"
    (root / "one" / "two").mkdir(parents=True)
    (root / "one" / "two" / "cache").write_text("x")
    opened: list[int] = []
    closed: list[int] = []
    original_close, original_parent, original_relative = native._close, native._open_parent, native._open_relative
    monkeypatch.setattr(native, "_open_parent", lambda path: (opened.append(handle := original_parent(path)), handle)[1])
    monkeypatch.setattr(native, "_open_relative", lambda parent, name, directory: (opened.append(handle := original_relative(parent, name, directory)), handle)[1])
    monkeypatch.setattr(native, "_close", lambda handle: (closed.append(handle), original_close(handle))[1])
    monkeypatch.setattr(native, "_delete", lambda handle: (_ for _ in ()).throw(OSError("injected delete failure")))
    assert not native.delete_directory(str(root))
    def value(handle):
        return handle.value if hasattr(handle, "value") else handle
    assert len(opened) >= 3 and sorted(map(value, opened)) == sorted(map(value, closed))


def test_root_swap_is_refused_and_outside_is_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, outside = tmp_path / "state", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "keep").write_text("outside")
    original, swapped = native._open_relative, False
    def swap(parent, name, directory):
        nonlocal swapped
        handle = original(parent, name, directory)
        if name == "state" and not swapped:
            swapped = True
            root.rename(tmp_path / "old-state")
            _junction(root, outside)
        return handle
    monkeypatch.setattr(native, "_open_relative", swap)
    assert not native.delete_directory(str(root))
    assert swapped and (outside / "keep").read_text() == "outside"


def test_descendant_swap_and_reparse_are_refused_without_outside_deletion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, child, outside = tmp_path / "state", tmp_path / "state" / "child", tmp_path / "outside"
    child.mkdir(parents=True)
    outside.mkdir()
    (outside / "keep").write_text("outside")
    original, swapped = native._open_relative, False
    def swap(parent, name, directory):
        nonlocal swapped
        handle = original(parent, name, directory)
        if name == "child" and not swapped:
            swapped = True
            child.rename(root / "old-child")
            _junction(child, outside)
        return handle
    monkeypatch.setattr(native, "_open_relative", swap)
    assert not native.delete_directory(str(root))
    assert swapped and (outside / "keep").read_text() == "outside"


def test_existing_reparse_is_refused_and_old_pathname_strategy_is_insufficient(tmp_path: Path) -> None:
    root, outside = tmp_path / "state", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "keep").write_text("outside")
    _junction(root / "linked", outside)
    assert not native.delete_directory(str(root))
    assert (outside / "keep").read_text() == "outside"
    # The old strategy's pathname walk would traverse a junction; it is test-only.
    def unsafe_pathname_delete(path: Path) -> None:
        for entry in path.iterdir():
            if entry.is_dir():
                unsafe_pathname_delete(entry)
            else:
                entry.unlink()
    unsafe_pathname_delete(root)
    assert not (outside / "keep").exists()


def test_unavailable_native_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "state"
    root.mkdir()
    monkeypatch.setattr(native, "_api", lambda: None)
    assert not native.delete_directory(str(root)) and root.exists()
