"""Native cache path regressions; logical identities and coordination stay fixed."""
import hashlib
import json
import os
import stat
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pytest

from tests.test_cache import config, context, public_bytes
from yasb_limitora import cache as cache_module
from yasb_limitora.cache import RefreshCoordinator, SingleFlightResult, cache_path
from yasb_limitora.deadline import DeadlineContext


def _coordinator(tmp_path, marker_length, *, suffix="", **options):
    # Keep the native regression length independent of the checkout location.
    parent = tmp_path.parent
    desired = marker_length - len("\\yasb-limitora\\") - 97
    width = desired - len(str(parent)) - 1
    label = hashlib.sha256(tmp_path.name.encode()).hexdigest()[:8]
    assert width >= len(label), "owned test root is too long for this native control"
    local = parent / (label + "k" * (width - len(label)))
    environment = {"LOCALAPPDATA": str(local)}
    path = tmp_path / ("config" + suffix + ".json")
    result = RefreshCoordinator(config(path), environment, path, **options)
    assert len(result.marker_path) == marker_length
    assert result.marker_path == result.path + ".refresh.json"
    assert result.fingerprint in result.path
    return result


def _short_control_root(tmp_path, request):
    # Only the 240-character controls need a fallback when TEMP exhausts their budget.
    desired = 240 - len("\\yasb-limitora\\") - 97
    if desired - len(str(tmp_path.parent)) - 1 >= 8:
        return tmp_path
    parent = Path(__file__).resolve().parents[1] / "tmp"
    parent.mkdir(exist_ok=True)
    owned = TemporaryDirectory(prefix="c1-", dir=parent)
    request.addfinalizer(owned.cleanup)
    control = Path(owned.name) / tmp_path.name
    control.mkdir()
    return control


def _native(path):
    # Fixture-only access seeds the SAME existing file, not an alternate layout.
    return Path("\\\\?\\" + str(path))


def _producer(calls):
    def produce(_context):
        calls.append(True)
        return SingleFlightResult(value="fresh", cached_public_bytes=public_bytes(), produced=True)
    return produce


@pytest.mark.skipif(os.name != "nt", reason="native Windows cache path regression")
@pytest.mark.parametrize("marker_length", (240, 260, 280))
def test_native_refresh_publishes_and_reuses_exact_legacy_paths(tmp_path, marker_length, request):
    if marker_length == 240:
        tmp_path = _short_control_root(tmp_path, request)
    cache = _coordinator(tmp_path, marker_length)
    calls = []
    result = cache.get_or_refresh(context(), _producer(calls))
    assert result.value == "fresh" and result.produced and not result.coordination_failed
    assert calls == [True]
    assert cache.load(context()) == public_bytes()
    hit = cache.get_or_refresh(context(), _producer(calls))
    assert hit.cached_public_bytes == public_bytes() and not hit.produced
    assert calls == [True]
    marker = json.loads(_native(cache.marker_path).read_bytes())
    assert marker["owner_pid"] == 0 and marker["owner_token"] == ""
    assert marker["generation"] == 1
    assert not list(_native(Path(cache.path).parent).glob(".quota-v2-*.tmp"))


@pytest.mark.skipif(os.name != "nt", reason="native Windows cache path regression")
def test_native_distinct_keys_do_not_collide_at_long_marker_paths(tmp_path):
    first = _coordinator(tmp_path, 260, suffix="a")
    second = _coordinator(tmp_path, 260, suffix="b")
    assert Path(first.path).parent == Path(second.path).parent
    assert first.fingerprint != second.fingerprint
    assert first.path != second.path and first.marker_path != second.marker_path
    calls = []
    for cache in (first, second):
        assert cache.get_or_refresh(context(), _producer(calls)).produced
        assert cache.load(context()) == public_bytes()
    assert calls == [True, True]
    for cache in (first, second):
        marker = json.loads(_native(cache.marker_path).read_bytes())
        assert marker["generation"] == 1 and marker["owner_pid"] == 0


def _seed_marker(cache, token):
    target = _native(cache.marker_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps({"generation": 7, "owner_pid": os.getpid(), "owner_token": token,
                       "started_at": "2026-10-13T00:00:00.000000Z"},
                      ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False) + "\n").encode()
    target.write_bytes(raw)
    return raw


@pytest.mark.skipif(os.name != "nt", reason="native Windows cache path regression")
def test_native_legacy_live_owner_is_not_bypassed(tmp_path):
    now = [0]
    def expire_wait(_seconds):
        now[0] = 5_000_000_000
    cache = _coordinator(tmp_path, 260, process_token=lambda _pid: "current", sleep=expire_wait)
    raw = _seed_marker(cache, "current")
    calls = []
    budget = DeadlineContext.from_seconds(5, t0_ns=0, clock_ns=lambda: now[0])
    result = cache.get_or_refresh(budget, _producer(calls))
    assert not result.produced and result.deadline_exhausted
    assert not result.coordination_failed
    assert calls == []
    assert _native(cache.marker_path).read_bytes() == raw
    assert not _native(cache.path).exists()


@pytest.mark.skipif(os.name != "nt", reason="native Windows cache path regression")
def test_native_legacy_dead_owner_is_reclaimed_and_cleaned(tmp_path):
    cache = _coordinator(tmp_path, 260, process_token=lambda _pid: "current")
    _seed_marker(cache, "previous")
    calls = []
    result = cache.get_or_refresh(context(), _producer(calls))
    assert result.value == "fresh" and result.produced and calls == [True]
    marker = json.loads(_native(cache.marker_path).read_bytes())
    assert marker["generation"] == 8
    assert marker["owner_pid"] == 0 and marker["owner_token"] == ""
    assert cache.load(context()) == public_bytes()


@pytest.mark.skipif(os.name != "nt", reason="native Windows cache path regression")
def test_native_cleanup_of_unpublished_claim_preserves_generation(tmp_path):
    cache = _coordinator(tmp_path, 260)
    decision = cache.claim_or_wait(cache.inspect_state(context()), context())
    assert decision.claim is not None and decision.result is None and not decision.wait
    assert cache.cleanup_attempt(decision.claim, context()) is None
    marker = json.loads(_native(cache.marker_path).read_bytes())
    assert marker["generation"] == decision.claim.generation == 1
    assert marker["owner_pid"] == 0 and marker["owner_token"] == ""
    assert cache.load(context()) is None and not _native(cache.path).exists()
    assert not list(_native(Path(cache.path).parent).glob(".quota-v2-*.tmp"))


@pytest.mark.skipif(os.name != "nt", reason="native Windows cache path regression")
def test_native_replace_error_is_not_hidden_by_produced_success(tmp_path, monkeypatch):
    cache = _coordinator(tmp_path, 260)
    monkeypatch.setattr(cache_module, "_bounded_call", lambda fn, args, _budget: fn(*args))
    attempts = []
    def denied(source, destination):
        attempts.append((source, destination))
        raise PermissionError(13, "synthetic denial")
    monkeypatch.setattr(cache_module.os, "replace", denied)
    calls = []
    result = cache.get_or_refresh(context(), _producer(calls))
    assert result.coordination_failed and result.coordination_error == "internal_error"
    assert not result.produced and result.cached_public_bytes is None and calls == []
    assert len(attempts) == 1
    assert not _native(cache.marker_path).exists() and not _native(cache.path).exists()
    assert not list(_native(Path(cache.path).parent).glob(".quota-v2-*.tmp"))


@pytest.mark.skipif(os.name != "nt", reason="native Windows cache path regression")
def test_native_long_existing_reparse_target_is_rejected(tmp_path, monkeypatch):
    cache = _coordinator(tmp_path, 260)
    _seed_marker(cache, "current")
    original = os.lstat
    seen = []
    native_target = str(_native(cache.marker_path))
    def metadata(path, *args, **kwargs):
        if str(path) == native_target:
            seen.append(True)
            return SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(cache_module.os, "lstat", metadata)
    monkeypatch.setattr(cache_module, "_bounded_call", lambda fn, args, _budget: fn(*args))
    calls = []
    result = cache.get_or_refresh(context(), _producer(calls))
    assert seen and result.coordination_failed and not result.produced and calls == []
    assert not _native(cache.path).exists()


def test_non_windows_io_keeps_paths_unmodified(tmp_path, monkeypatch):
    real_replace = os.replace
    seen = []
    def replace(source, destination):
        seen.append((source, destination))
        return real_replace(source, destination)
    monkeypatch.setattr(cache_module, "os", SimpleNamespace(**{**vars(os), "name": "posix", "replace": replace}))
    target = str(tmp_path / "state.json")
    cache_module._cache_write_child(target, b"bounded")
    assert cache_module._cache_read_child(target) == b"bounded"
    assert len(seen) == 1 and seen[0][1] == target
    assert not str(seen[0][0]).startswith("\\\\?\\")


def test_extended_prefix_is_not_a_new_accepted_logical_input(tmp_path):
    with pytest.raises(ValueError):
        cache_path("\\\\?\\C:\\state\\config.json", {"LOCALAPPDATA": str(tmp_path)})
