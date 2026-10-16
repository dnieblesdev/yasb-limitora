"""Hermetic checks of the scanner, without importing the native proof module."""

import ast
import hashlib
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def scan():
    source = Path(__file__).with_name("test_windows_native_proof.py")
    tree = ast.parse(source.read_text(encoding="utf-8"))
    node = next(
        item for item in tree.body
        if isinstance(item, ast.FunctionDef)
        and item.name == "_assert_artifacts_are_sentinel_free"
    )
    namespace = {"Path": Path, "stat": stat, "hashlib": hashlib}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[node.name]


def file_entry(name, content):
    return {"name": name, "type": "file", "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest()}


def test_single_file_preserved(scan, tmp_path):
    path = tmp_path / "regular.txt"
    path.write_bytes(b"safe")
    assert scan((path,), "SENTINEL") == [file_entry("regular.txt", b"safe")]
    assert path.read_bytes() == b"safe"


def test_mixed_tree_and_empty_directory_never_read_bytes(scan, tmp_path, monkeypatch):
    root = tmp_path / "artifacts"
    root.mkdir()
    empty = root / "empty"
    empty.mkdir()
    nested = root / "nested"
    nested.mkdir()
    leaf = nested / "leaf.txt"
    leaf.write_bytes(b"nested safe")
    sibling = tmp_path / "sibling.txt"
    sibling.write_bytes(b"safe")
    original = Path.read_bytes
    reads = []

    def read(path):
        assert path not in (root, empty, nested), "directory read_bytes called"
        reads.append(path)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    assert scan((root, sibling), "SENTINEL") == [
        {"name": "artifacts", "type": "directory"},
        {"name": "artifacts/empty", "type": "directory"},
        {"name": "artifacts/nested", "type": "directory"},
        file_entry("artifacts/nested/leaf.txt", b"nested safe"),
        file_entry("sibling.txt", b"safe"),
    ]
    assert reads == [leaf, sibling]
    assert original(leaf) == b"nested safe"


@pytest.mark.parametrize("nested", [False, True])
def test_privacy_failure_fixed_message(scan, tmp_path, nested):
    root = tmp_path / "artifacts"
    root.mkdir()
    path = root / "private.txt"
    path.write_bytes(b"prefix SENTINEL suffix")
    with pytest.raises(AssertionError) as error:
        scan((root if nested else path,), "SENTINEL")
    assert str(error.value) == "native proof artifact scan failed"
    assert "SENTINEL" not in str(error.value)
    assert path.read_bytes() == b"prefix SENTINEL suffix"


@pytest.mark.parametrize("operation", ["read_bytes", "iterdir", "lstat"])
def test_actual_errors_propagate_identity(scan, tmp_path, monkeypatch, operation):
    path = tmp_path / "artifact"
    if operation == "iterdir":
        path.mkdir()
    else:
        path.write_bytes(b"safe")
    failure = PermissionError("controlled inaccessible artifact")
    original = getattr(Path, operation)

    def fail(target, *args, **kwargs):
        if target == path:
            raise failure
        return original(target, *args, **kwargs)

    monkeypatch.setattr(Path, operation, fail)
    with pytest.raises(PermissionError) as error:
        scan((path,), "SENTINEL")
    assert error.value is failure
    if operation != "iterdir":
        assert path.open("rb").read() == b"safe"


@pytest.mark.parametrize("mode,attributes", [
    (stat.S_IFLNK, 0), (stat.S_IFDIR, 0x400),
    (stat.S_IFREG, 0x400), (stat.S_IFIFO, 0),
])
def test_unsafe_types_fail_closed_without_traversal(scan, tmp_path, monkeypatch, mode, attributes):
    path = tmp_path / "unsafe"
    path.write_bytes(b"safe")
    original = Path.lstat

    def metadata(target):
        if target == path:
            return SimpleNamespace(st_mode=mode, st_file_attributes=attributes)
        return original(target)

    def poison(target):
        pytest.fail("unsafe artifact read or traversed")

    monkeypatch.setattr(Path, "lstat", metadata)
    monkeypatch.setattr(Path, "read_bytes", poison)
    monkeypatch.setattr(Path, "iterdir", poison)
    with pytest.raises(AssertionError) as error:
        scan((path,), "SENTINEL")
    assert str(error.value) == "native proof artifact scan failed"
    with path.open("rb") as stream:
        assert stream.read() == b"safe"
