"""Regression coverage for the derived mkstemp path, not a new persisted layout."""
import json
import ntpath
import os
from pathlib import Path

import pytest

from tests.test_cache import context, public_bytes
from tests.test_cache_native_paths import _coordinator, _native, _producer
from yasb_limitora import cache as cache_module


def _units(value):
    return len(value.encode("utf-16-le", errors="surrogatepass")) // 2


@pytest.mark.skipif(os.name != "nt", reason="native Windows temporary path boundary")
@pytest.mark.parametrize("directory_units", (142, 236, *range(237, 248), 248, 250))
def test_temporary_path_boundary_publishes_without_leftovers(tmp_path, monkeypatch, directory_units):
    cache = _coordinator(tmp_path, directory_units + 98)
    directory = str(Path(cache.path).parent)
    assert _units(directory) == directory_units
    monkeypatch.setattr(cache_module, "_bounded_call", lambda fn, args, _budget: fn(*args))
    original_open = os.open
    shapes = []
    def opened(path, flags, *args, **kwargs):
        name = ntpath.basename(path)
        if not name.startswith(cache_module._CACHE_TEMP_PREFIX):
            return original_open(path, flags, *args, **kwargs)
        literal = str(path)
        logical = literal[4:] if literal.startswith("\\\\?\\") else literal
        row = {"directory_units": directory_units, "join_units": 1,
               "prefix_units": _units(cache_module._CACHE_TEMP_PREFIX),
               "random_units": _units(name) - _units(cache_module._CACHE_TEMP_PREFIX) - _units(cache_module._CACHE_TEMP_SUFFIX),
               "suffix_units": _units(cache_module._CACHE_TEMP_SUFFIX),
               "temporary_units": _units(logical), "native_argument": literal.startswith("\\\\?\\"),
               "same_logical_directory": ntpath.dirname(logical) == directory}
        shapes.append(row)
        try:
            return original_open(path, flags, *args, **kwargs)
        except OSError as error:
            row["exception"] = {"type": type(error).__name__, "errno": error.errno,
                                "winerror": getattr(error, "winerror", None)}
            raise
    monkeypatch.setattr(cache_module.os, "open", opened)
    published = cache.publish(public_bytes(), context())
    (tmp_path / "temporary-shape.json").write_text(json.dumps(shapes, indent=2) + "\n")
    assert len(shapes) == 1 and shapes[0]["same_logical_directory"]
    assert shapes[0]["temporary_units"] == directory_units + 1 + shapes[0]["prefix_units"] + shapes[0]["random_units"] + shapes[0]["suffix_units"]
    assert published
    assert cache.load(context()) == public_bytes()
    assert not _native(cache.marker_path).exists()
    assert not list(_native(directory).glob(".quota-v2-*.tmp"))


@pytest.mark.skipif(os.name != "nt", reason="native Windows temporary path boundary")
def test_temporary_boundary_coexists_with_native_marker_publication(tmp_path):
    cache = _coordinator(tmp_path, 247 + 98)
    calls = []
    result = cache.get_or_refresh(context(), _producer(calls))
    assert result.produced and result.value == "fresh" and not result.coordination_failed
    assert calls == [True] and cache.load(context()) == public_bytes()
    marker = json.loads(_native(cache.marker_path).read_bytes())
    assert marker["generation"] == 1 and marker["owner_pid"] == 0 and marker["owner_token"] == ""
    assert cache.marker_path == cache.path + ".refresh.json"
    assert cache.fingerprint in cache.path
    assert not list(_native(Path(cache.path).parent).glob(".quota-v2-*.tmp"))


@pytest.mark.skipif(os.name != "nt", reason="native Windows temporary path boundary")
def test_overlapping_temporary_reservations_do_not_collide(tmp_path, monkeypatch):
    first = _coordinator(tmp_path, 237 + 98, suffix="first")
    second = _coordinator(tmp_path, 237 + 98, suffix="second")
    assert Path(first.path).parent == Path(second.path).parent and first.path != second.path
    monkeypatch.setattr(cache_module, "_bounded_call", lambda fn, args, _budget: fn(*args))
    original_replace = os.replace
    reservations = []
    def replaced(source, destination):
        reservations.append(str(source))
        assert Path(source).is_file()
        if len(reservations) == 1:
            assert second.publish(public_bytes(), context())
            assert Path(source).is_file()
        else:
            assert len(reservations) == 2 and reservations[0] != reservations[1]
            assert Path(reservations[0]).is_file()
        return original_replace(source, destination)
    monkeypatch.setattr(cache_module.os, "replace", replaced)
    assert first.publish(public_bytes(), context())
    assert len(reservations) == 2 and len(set(reservations)) == 2
    assert first.load(context()) == second.load(context()) == public_bytes()
    assert not list(_native(Path(first.path).parent).glob(".quota-v2-*.tmp"))


@pytest.mark.skipif(os.name != "nt", reason="native Windows temporary path boundary")
def test_failed_replace_cleans_long_temporary_without_changing_stored_data(tmp_path, monkeypatch):
    cache = _coordinator(tmp_path, 247 + 98)
    assert cache.publish(public_bytes(), context())
    monkeypatch.setattr(cache_module, "_bounded_call", lambda fn, args, _budget: fn(*args))
    attempts = []
    def denied(source, destination):
        attempts.append(True)
        assert Path(source).is_file()
        raise PermissionError(13, "synthetic denial")
    monkeypatch.setattr(cache_module.os, "replace", denied)
    assert not cache.publish(public_bytes(), context())
    assert attempts == [True]
    assert cache.load(context()) == public_bytes()
    assert not _native(cache.marker_path).exists()
    assert not list(_native(Path(cache.path).parent).glob(".quota-v2-*.tmp"))
