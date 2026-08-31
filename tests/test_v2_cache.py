import json
import os
import threading
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from tests.test_json_v2_projection import _near_boundary_document
from yasb_limitora.config import LocalConfig
from yasb_limitora.model import (
    DocumentView,
    ProviderKey,
    ProviderOutcome,
    ProviderSnapshotView,
    ProviderState,
    ProviderView,
    PublicProviderState,
    QuotaAvailability,
    QuotaMetricKind,
    QuotaQuantity,
    QuotaWindowKind,
    QuotaWindowView,
    SafeError,
    SafeErrorCode,
    SnapshotFreshness,
)
from yasb_limitora.projection_v2 import V2ProjectionInput, project_v2_bytes
from yasb_limitora.v2_cache import (
    CACHE_TTL_SECONDS,
    OwnerState,
    RefreshCoordinator,
    RefreshState,
    SingleFlightResult,
    V2QuotaCache,
)
from yasb_limitora.v2_deadline import DeadlineContext
from yasb_limitora.v2_guard import GuardError


def _loaded(value: bytes | None) -> bytes:
    assert value is not None
    return value


def context(seconds=5):
    return DeadlineContext.from_seconds(seconds, t0_ns=0, clock_ns=lambda: 0)


def config(path, *, opencode=False, runner=r"C:\\codex.exe"):
    return LocalConfig.from_mapping(
        {
            "codex": {"enabled": True, "runner": runner},
            "opencode_go": {"enabled": opencode},
        }
    )


def public_bytes(*, cleanup=False, provider_error=False, disabled=False):
    codex = ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.UNDETECTED)
    if provider_error:
        codex = ProviderView(
            ProviderKey.CODEX,
            ProviderState.SAFE_ERROR,
            SafeError(SafeErrorCode.PROVIDER_ERROR),
            outcome=ProviderOutcome.EXECUTION_ERROR,
        )
    opencode = ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.NOT_RUN, not_run_reason="disabled")
    if not disabled:
        opencode = ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.UNDETECTED)
    error = SafeError(SafeErrorCode.CLEANUP_FAILED) if cleanup else None
    return project_v2_bytes(V2ProjectionInput(DocumentView.ordered(codex, opencode, error), frozenset({ProviderKey.CODEX, ProviderKey.OPENCODE_GO})))


def mixed_not_run_public_bytes(reason):
    return project_v2_bytes(
        V2ProjectionInput(
            DocumentView.ordered(
                ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.UNDETECTED),
                ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.NOT_RUN, not_run_reason=reason),
            ),
            frozenset({ProviderKey.CODEX, ProviderKey.OPENCODE_GO}),
        )
    )

def snapshot_public_bytes(scope="account"):
    now = datetime(2026, 8, 15, tzinfo=timezone.utc)
    window = QuotaWindowView(
        QuotaWindowKind.COMMERCIAL_QUOTA,
         scope,
        "weekly",
        None,
        QuotaAvailability.KNOWN,
        "codex-app-server-v2",
        QuotaQuantity(Decimal(100), QuotaMetricKind.COMMERCIAL_QUOTA, "requests"),
        QuotaQuantity(Decimal(25), QuotaMetricKind.COMMERCIAL_QUOTA, "requests"),
        QuotaQuantity(Decimal(75), QuotaMetricKind.COMMERCIAL_QUOTA, "requests"),
    )
    snapshot = ProviderSnapshotView(
        PublicProviderState.PARTIAL,
        SnapshotFreshness.FRESH,
        now,
        now,
        now,
        "codex-app-server-v2",
        (window,),
    )
    return project_v2_bytes(
        V2ProjectionInput(
            DocumentView.ordered(
                ProviderView(ProviderKey.CODEX, ProviderState.SUCCESS, outcome=ProviderOutcome.SNAPSHOT, snapshot=snapshot),
                ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.UNDETECTED),
            ),
            frozenset({ProviderKey.CODEX}),
        )
    )


def make_cache(tmp_path, *, now=None, runner=r"C:\\codex.exe", key="private-key"):
    target = tmp_path / "config.json"
    target.write_text("{}", encoding="utf-8")
    value = LocalConfig.from_mapping({"codex": {"enabled": True, "runner": runner}, "opencode_go": {}})
    environment = {"LOCALAPPDATA": str(tmp_path), "LIMITORA_OPENCODE_API_KEY": key}
    return V2QuotaCache(value, environment, target, now=now), target


def test_refresh_coordinator_construction_is_lookup_free(monkeypatch, tmp_path):
    from yasb_limitora import v2_cache

    target = tmp_path / "config.json"
    environment = {"LOCALAPPDATA": str(tmp_path), "LIMITORA_OPENCODE_API_KEY": "private-key"}

    def fail_lookup(*args, **kwargs):
        raise AssertionError("constructor performed filesystem lookup")

    monkeypatch.setattr(v2_cache.os, "lstat", fail_lookup)
    monkeypatch.setattr(v2_cache.os.path, "isdir", fail_lookup)
    monkeypatch.setattr(v2_cache.os.path, "exists", fail_lookup)

    cache = RefreshCoordinator(config(target), environment, target)

    assert cache.path.endswith(".json")


def test_cache_round_trip_is_public_only_and_refreshes_identical_provider_text(tmp_path):
    now = datetime(2026, 8, 15, tzinfo=timezone.utc)
    cache, _ = make_cache(tmp_path, now=lambda: now)
    document = snapshot_public_bytes()

    assert cache.publish(document, context())
    loaded = cache.load(context())
    assert loaded == document
    raw = cache.path
    contents = Path(raw).read_text(encoding="utf-8")
    assert "private-key" not in contents
    assert "codex.exe" not in contents
    assert "config.json" not in contents
    envelope = json.loads(contents)
    assert set(envelope) == {"schema", "cached_at", "fingerprint", "document"}
    assert len(envelope["fingerprint"]) == 64


def test_schema_two_cache_is_a_cold_miss_and_refreshes_once(tmp_path):
    cache, _ = make_cache(tmp_path)
    document = public_bytes()
    envelope = {
        "schema": 2,
        "cached_at": "2026-08-15T00:00:00.000000Z",
        "fingerprint": cache.fingerprint,
        "document": json.loads(document),
    }
    Path(cache.path).parent.mkdir(parents=True, exist_ok=True)
    Path(cache.path).write_bytes((json.dumps(envelope, separators=(",", ":")) + "\n").encode())
    calls = []

    def producer(_context):
        calls.append(True)
        return SingleFlightResult(value="fresh", cached_public_bytes=document, produced=True)

    result = cache.get_or_refresh(context(), producer)

    assert result.produced and calls == [True]
    assert cache.load(context()) == document
    assert json.loads(Path(cache.path).read_text())["schema"] == 3


def test_cache_rejects_current_payload_with_inserted_root_version(tmp_path):
    cache, _ = make_cache(tmp_path)
    document = public_bytes()
    assert cache.publish(document, context())
    envelope = json.loads(Path(cache.path).read_text())
    envelope["document"] = {"version": 2, **envelope["document"]}
    Path(cache.path).write_bytes((json.dumps(envelope, separators=(",", ":")) + "\n").encode())

    assert cache.load(context()) is None


def test_cache_hit_preserves_public_document_root_order(tmp_path):
    cache, _ = make_cache(tmp_path)
    assert cache.publish(public_bytes(), context())
    loaded = cache.load(context())
    assert loaded is not None
    assert list(json.loads(loaded).keys()) == ["execution_state", "execution_error", "providers"]


@pytest.mark.parametrize("mutate", ("root", "provider", "window", "quantity", "depleted", "error"))
def test_cache_rejects_reordered_public_nested_mappings(tmp_path, mutate):
    cache, _ = make_cache(tmp_path)
    document_bytes = snapshot_public_bytes()
    assert cache.publish(document_bytes, context())
    envelope = json.loads(Path(cache.path).read_text(encoding="utf-8"))
    document = envelope["document"]
    def reorder(value):
        return {key: value[key] for key in reversed(tuple(value))}
    mutators = {
        "root": lambda: envelope.update(document=reorder(document)),
        "provider": lambda: document["providers"].__setitem__(0, reorder(document["providers"][0])),
        "window": lambda: document["providers"][0]["windows"].__setitem__(0, reorder(document["providers"][0]["windows"][0])),
        "quantity": lambda: document["providers"][0]["windows"][0].__setitem__("limit", reorder(document["providers"][0]["windows"][0]["limit"])),
        "depleted": lambda: document["providers"][0].__setitem__("most_depleted_window", reorder(document["providers"][0]["most_depleted_window"])),
        "error": lambda: (
            document.__setitem__("execution_state", "execution_error"),
            document.__setitem__("execution_error", {"phase": "cleanup", "code": "cleanup_failed"}),
        ),
    }
    mutators[mutate]()
    Path(cache.path).write_bytes((json.dumps(envelope, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    assert cache.load(context()) is None


def test_get_or_refresh_cache_hit_stops_before_attempt(tmp_path):
    cache, _ = make_cache(tmp_path)
    cached = public_bytes()
    assert isinstance(cache, RefreshCoordinator)
    assert cache.publish(cached, context())
    calls = []

    result = cache.get_or_refresh(context(), lambda _: calls.append(True))

    assert result.cached_public_bytes == cached
    assert calls == []


def test_cache_ttl_and_fingerprint_and_path_mismatch_fail_closed(tmp_path):
    now = [datetime(2026, 8, 15, tzinfo=timezone.utc)]
    cache, target = make_cache(tmp_path, now=lambda: now[0])
    assert cache.publish(public_bytes(), context())
    now[0] += timedelta(seconds=CACHE_TTL_SECONDS + 1)
    assert cache.load(context()) is None
    now[0] -= timedelta(seconds=CACHE_TTL_SECONDS + 1)

    environment = {"LOCALAPPDATA": str(tmp_path), "LIMITORA_OPENCODE_API_KEY": "private-key"}
    other = V2QuotaCache(config(target, runner=r"C:\\other.exe"), environment, target, now=lambda: now[0])
    assert other.load(context()) is None
    other_path = tmp_path / "other.json"
    other_path.write_text("{}", encoding="utf-8")
    different_path = V2QuotaCache(config(target), environment, other_path, now=lambda: now[0])
    assert different_path.load(context()) is None


def test_effective_fingerprint_is_part_of_physical_cache_identity(tmp_path):
    target = tmp_path / "config.json"
    target.write_text("{}", encoding="utf-8")
    environment = {"LOCALAPPDATA": str(tmp_path), "LIMITORA_OPENCODE_API_KEY": "private-key"}
    first = V2QuotaCache(config(target, runner=r"C:\\first.exe"), environment, target)
    second = V2QuotaCache(config(target, runner=r"C:\\second.exe"), environment, target)

    assert first.path != second.path
    assert first.fingerprint in first.path
    assert second.fingerprint in second.path
    assert first.publish(public_bytes(), context())
    assert second.publish(snapshot_public_bytes(), context())
    assert json.loads(_loaded(first.load(context()))) == json.loads(public_bytes())
    assert json.loads(_loaded(second.load(context()))) == json.loads(snapshot_public_bytes())


def test_distinct_config_paths_use_distinct_cache_files_and_create_directory(tmp_path):
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first_path.write_text("{}", encoding="utf-8")
    second_path.write_text("{}", encoding="utf-8")
    environment = {"LOCALAPPDATA": str(tmp_path / "missing-localappdata"), "LIMITORA_OPENCODE_API_KEY": "private-key"}
    first = V2QuotaCache(config(first_path), environment, first_path)
    second = V2QuotaCache(config(second_path), environment, second_path)

    assert first.path != second.path
    assert first.publish(public_bytes(), context())
    assert second.publish(snapshot_public_bytes(), context())
    assert json.loads(_loaded(first.load(context()))) == json.loads(public_bytes())
    assert json.loads(_loaded(second.load(context()))) == json.loads(snapshot_public_bytes())


@pytest.mark.parametrize(
    "mutate",
    (
        lambda raw: raw[:-1] + b" ",
        lambda raw: raw.replace(b'"schema":3', b'"schema":3,"schema":3', 1),
        lambda raw: b"{" + b"x" * 131_073,
        lambda raw: raw.replace(b'"execution_error":null', b'"execution_error":{"code":"provider_failed","phase":"provider"}', 1),
        lambda raw: raw.replace(b'"compact_text":"Quota not detected"', b'"compact_text":"C:\\\\secret\\\\token"', 1),
    ),
)
def test_corrupt_oversize_duplicate_noncanonical_and_unsafe_cache_is_ignored(tmp_path, mutate):
    now = datetime(2026, 8, 15, tzinfo=timezone.utc)
    cache, _ = make_cache(tmp_path, now=lambda: now)
    assert cache.publish(public_bytes(), context())
    original = Path(cache.path).read_bytes()
    with open(cache.path, "wb") as output:
        output.write(mutate(original))
    assert cache.load(context()) is None


def _make_unordered_timestamps(document):
    provider = document["providers"][0]
    provider["status_observed_at"] = "2026-08-15T00:00:00.000001Z"
    provider["fetched_at"] = "2026-08-15T00:00:00.000000Z"


def _make_incomplete_document_error(document):
    document["execution_error"] = {"code": "cleanup_failed", "phase": "cleanup"}


def _make_inconsistent_provider_source(document):
    document["providers"][0]["source_id"] = "opencode-go-api"


def _make_inconsistent_document_state(document):
    document["execution_state"] = "not_run"


@pytest.mark.parametrize(
    "mutate",
    (
        lambda document: document["providers"][0]["windows"][0]["limit"].update(value="100.0"),
        lambda document: document["providers"][0]["windows"][0]["used"].update(metric="technical_rate_limit"),
        lambda document: document["providers"][0]["windows"][0]["remaining"].update(unit="tokens"),
        lambda document: document["providers"][0]["windows"][0]["used"].update(value="20"),
        lambda document: document["providers"][0]["windows"][0]["used"].update(value="125"),
        _make_unordered_timestamps,
        _make_incomplete_document_error,
        _make_inconsistent_provider_source,
        _make_inconsistent_document_state,
    ),
)
def test_cache_rejects_semantic_corruption_before_returning_bytes(tmp_path, mutate):
    now = datetime(2026, 8, 15, tzinfo=timezone.utc)
    cache, _ = make_cache(tmp_path, now=lambda: now)
    assert cache.publish(snapshot_public_bytes(), context())
    envelope = json.loads(Path(cache.path).read_text(encoding="utf-8"))
    mutate(envelope["document"])
    with open(cache.path, "w", encoding="utf-8") as output:
        json.dump(envelope, output, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        output.write("\n")
    assert cache.load(context()) is None


def test_cache_rejects_unordered_timestamps_and_inconsistent_presentation(tmp_path):
    now = datetime(2026, 8, 15, tzinfo=timezone.utc)
    cache, _ = make_cache(tmp_path, now=lambda: now)
    assert cache.publish(snapshot_public_bytes(), context())
    envelope = json.loads(Path(cache.path).read_text(encoding="utf-8"))
    provider = envelope["document"]["providers"][0]
    provider["status_observed_at"] = "2026-08-15T00:00:00.000001Z"
    provider["fetched_at"] = "2026-08-15T00:00:00.000000Z"
    provider["compact_text"] = "tampered"
    with open(cache.path, "w", encoding="utf-8") as output:
        json.dump(envelope, output, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        output.write("\n")
    assert cache.load(context()) is None


def test_cache_rejects_provider_tooltip_from_independent_budget(tmp_path):
    cache, _ = make_cache(tmp_path)
    assert cache.publish(snapshot_public_bytes(), context())
    envelope = json.loads(Path(cache.path).read_text(encoding="utf-8"))
    envelope["document"]["providers"][0]["tooltip_text"] = "Codex\\nState: Partial · Fresh\\nLowest quota: 75% remaining"
    Path(cache.path).write_bytes((json.dumps(envelope, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    assert cache.load(context()) is None


def test_cache_accepts_projection_selected_shared_budget_near_cap(tmp_path):
    cache, _ = make_cache(tmp_path)
    document = project_v2_bytes(V2ProjectionInput(_near_boundary_document(40)))
    value = json.loads(document)
    assert len(document) <= 65_536
    assert value["execution_error"] is None
    assert all(provider["outcome"] == "snapshot" for provider in value["providers"])
    assert cache.publish(document, context())
    assert cache.load(context()) == document


def test_cache_transport_decompression_rejects_oversized_child_payload(monkeypatch):
    from yasb_limitora import v2_cache, v2_path

    payload = zlib.compress(b"x" * (v2_cache.MAX_CACHE_BYTES + 1))
    monkeypatch.setattr(v2_path, "_bounded_file_call", lambda *args: payload)

    with pytest.raises(v2_cache.V2FileError):
        v2_cache._bounded_call(v2_cache._cache_read_child, ("unused",), context())


def test_cache_rejects_secret_like_quantity_unit_after_presentation_recompute(tmp_path):
    cache, _ = make_cache(tmp_path)
    assert cache.publish(snapshot_public_bytes(), context())
    envelope = json.loads(Path(cache.path).read_text(encoding="utf-8"))
    provider = envelope["document"]["providers"][0]
    unit = r"C:\secret\token"
    provider["windows"][0]["remaining"]["unit"] = unit
    provider["most_depleted_window"]["unit"] = unit
    Path(cache.path).write_bytes((json.dumps(envelope, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    assert cache.load(context()) is None


@pytest.mark.parametrize("scope", ("/private/path", r"\private\path"))
def test_cache_rejects_rooted_private_identity_forms(tmp_path, scope):
    now = datetime(2026, 8, 15, tzinfo=timezone.utc)
    cache, _ = make_cache(tmp_path, now=lambda: now)
    assert cache.publish(snapshot_public_bytes(), context())
    envelope = json.loads(Path(cache.path).read_text(encoding="utf-8"))
    envelope["document"]["providers"][0]["windows"][0]["scope"] = scope
    with open(cache.path, "w", encoding="utf-8") as output:
        json.dump(envelope, output, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        output.write("\n")
    assert cache.load(context()) is None


def test_cache_accepts_nonrooted_json_escaped_identity_text(tmp_path):
    now = datetime(2026, 8, 15, tzinfo=timezone.utc)
    cache, _ = make_cache(tmp_path, now=lambda: now)
    document = snapshot_public_bytes(scope=r"team\\west")
    assert cache.publish(document, context())
    assert cache.load(context()) == document


def test_cache_account_identity_lookup_failure_fails_closed(monkeypatch):
    from yasb_limitora import v2_cache, v2_guard

    monkeypatch.setattr(v2_cache.os, "name", "nt")
    monkeypatch.setattr(v2_guard, "_default_sid_bytes", lambda: b"")
    with pytest.raises(v2_cache.V2FileError):
        v2_cache._account_digest({})


@pytest.mark.parametrize("reason", ("deadline_exhausted", "guard_wait_timeout"))
def test_cache_rejects_transient_not_run_in_mixed_partial_document(tmp_path, reason):
    now = datetime(2026, 8, 15, tzinfo=timezone.utc)
    cache, _ = make_cache(tmp_path, now=lambda: now)
    document = mixed_not_run_public_bytes(reason)

    assert json.loads(document)["execution_state"] == "partial"
    assert not cache.publish(document, context())
    assert not Path(cache.path).exists()

def test_cache_preserves_publishable_disabled_not_run_control(tmp_path):
    now = datetime(2026, 8, 15, tzinfo=timezone.utc)
    cache, _ = make_cache(tmp_path, now=lambda: now)

    assert cache.publish(public_bytes(disabled=True), context())
    assert Path(cache.path).exists()

def test_cache_rejects_provider_errors_cleanup_and_all_disabled_results(tmp_path):
    now = datetime(2026, 8, 15, tzinfo=timezone.utc)
    cache, _ = make_cache(tmp_path, now=lambda: now)
    assert cache.publish(public_bytes(disabled=True), context())
    assert not cache.publish(public_bytes(provider_error=True), context())
    assert not cache.publish(public_bytes(cleanup=True), context())
    all_disabled = project_v2_bytes(
        V2ProjectionInput(
            DocumentView.ordered(
                ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.NOT_RUN, not_run_reason="disabled"),
                ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.NOT_RUN, not_run_reason="disabled"),
            ),
            frozenset(),
        )
    )
    assert not cache.publish(all_disabled, context())
    assert json.loads(_loaded(cache.load(context()))) == json.loads(public_bytes(disabled=True))


def test_cache_io_deadline_is_fail_closed(monkeypatch, tmp_path):
    cache, _ = make_cache(tmp_path)
    from yasb_limitora import v2_cache

    monkeypatch.setattr(v2_cache, "_bounded_call", lambda *args: (_ for _ in ()).throw(RuntimeError("blocked")))
    assert not cache.publish(public_bytes(), context())
    assert cache.load(context()) is None


def test_failed_writer_does_not_remove_another_context_temp(monkeypatch, tmp_path):
    cache, _ = make_cache(tmp_path)
    orphan = Path(cache.path).parent / ".quota-v2-orphan.tmp"
    orphan.parent.mkdir()
    orphan.write_bytes(b"partial")
    from yasb_limitora import v2_cache

    monkeypatch.setattr(v2_cache, "_bounded_call", lambda *args: (_ for _ in ()).throw(RuntimeError("writer stopped")))

    assert not cache.publish(public_bytes(), context())
    assert orphan.exists()


class _KeyLease:
    def __init__(self, lock):
        self.lock = lock
        self.released = False

    def release(self) -> bool:
        if not self.released:
            self.released = True
            self.lock.release()
        return True

    def close(self) -> bool:
        return True


class _KeyGuard:
    def __init__(self, lock):
        self.lock = lock

    def acquire_key(self, key: bytes, deadline: DeadlineContext) -> _KeyLease:
        self.lock.acquire()
        return _KeyLease(self.lock)


def _single_flight_cache(tmp_path, monkeypatch):
    cache, _ = make_cache(tmp_path)
    monkeypatch.setattr("yasb_limitora.v2_cache._bounded_call", lambda function, args, context: function(*args))
    lock = threading.Lock()
    monkeypatch.setattr(cache, "_guard_factory", lambda: _KeyGuard(lock))
    return cache


class _RetryLease:
    def __init__(self, release_results, close_results):
        self.owned = True
        self.closed = False
        self.release_results = iter(release_results)
        self.close_results = iter(close_results)
        self.release_calls = 0
        self.close_calls = 0

    def release(self) -> bool:
        self.release_calls += 1
        result = next(self.release_results)
        if result:
            self.owned = False
        return result

    def close(self) -> bool:
        self.close_calls += 1
        assert not self.owned
        result = next(self.close_results)
        if result:
            self.closed = True
        return result


def test_pending_lease_retries_release_before_closing(tmp_path, monkeypatch):
    cache = _single_flight_cache(tmp_path, monkeypatch)
    lease = _RetryLease((False, True), (True,))
    cast(Any, cache)._pending_lease = lease
    calls = []
    first = cache.get_or_refresh(context(), lambda _: calls.append("unexpected"))
    assert first.coordination_error == "internal_error"
    assert lease.release_calls == 1
    assert lease.close_calls == 0
    assert cache._pending_lease is lease
    assert calls == []

    second = cache.get_or_refresh(context(), lambda _: "fresh")

    assert second.value == "fresh"
    assert lease.release_calls == 2
    assert lease.close_calls == 1
    assert lease.closed
    assert getattr(lease, "_yasb_finalized", False)
    assert cache._pending_lease is None


def test_pending_lease_retries_only_close_after_release_succeeds(tmp_path, monkeypatch):
    cache = _single_flight_cache(tmp_path, monkeypatch)
    lease = _RetryLease((True,), (False, True))
    cast(Any, cache)._pending_lease = lease
    calls = []
    first = cache.get_or_refresh(context(), lambda _: calls.append("unexpected"))
    assert first.coordination_error == "internal_error"
    assert lease.release_calls == 1
    assert lease.close_calls == 1
    assert cache._pending_lease is lease
    assert calls == []

    second = cache.get_or_refresh(context(), lambda _: "fresh")

    assert second.value == "fresh"
    assert lease.release_calls == 1
    assert lease.close_calls == 2
    assert lease.closed
    assert getattr(lease, "_yasb_finalized", False)
    assert cache._pending_lease is None


def test_single_flight_live_producer_has_one_refresh_and_waiter_reads_publication(tmp_path, monkeypatch):
    cache = _single_flight_cache(tmp_path, monkeypatch)
    entered = threading.Event()
    release = threading.Event()
    calls = []
    results = []

    def producer(context):
        calls.append("refresh")
        entered.set()
        release.wait(1)
        return SingleFlightResult(value="producer", cached_public_bytes=public_bytes(), produced=True)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(cache.get_or_refresh, context(), producer)
        assert entered.wait(1)
        second = executor.submit(cache.get_or_refresh, context(), producer)
        release.set()
        results.extend((first.result(), second.result()))

    assert calls == ["refresh"]
    assert sorted(result.produced for result in results) == [False, True]
    assert any(result.value is None and result.cached_public_bytes is not None for result in results), results


def test_live_owner_waits_past_legacy_retry_ceiling_until_publication(tmp_path, monkeypatch):
    cache = _single_flight_cache(tmp_path, monkeypatch)
    waiter_cache, _ = make_cache(tmp_path)
    lock = threading.Lock()
    monkeypatch.setattr(waiter_cache, "_guard_factory", lambda: _KeyGuard(lock))
    fake_now = [0]
    wait_count = [0]
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def sleep(seconds):
        wait_count[0] += 1
        fake_now[0] += int(seconds * 1_000_000_000)
        if wait_count[0] == 257:
            release.set()

    monkeypatch.setattr(waiter_cache, "_sleep", sleep)
    original_inspect = waiter_cache.inspect_state

    def inspect_state(context):
        if wait_count[0] < 257:
            return RefreshState(owner_state=OwnerState.ALIVE)
        return original_inspect(context)

    monkeypatch.setattr(waiter_cache, "inspect_state", inspect_state)
    deadline = DeadlineContext.from_seconds(7, t0_ns=0, clock_ns=lambda: fake_now[0])

    def producer(context):
        calls.append("refresh")
        entered.set()
        assert release.wait(10)
        return SingleFlightResult(value="producer", cached_public_bytes=public_bytes(), produced=True)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(cache.get_or_refresh, deadline, producer)
        assert entered.wait(1)
        second = executor.submit(waiter_cache.get_or_refresh, deadline, lambda _: calls.append("duplicate"))
        results = (first.result(), second.result())

    assert wait_count[0] > 256
    assert calls == ["refresh"]
    assert sorted(result.produced for result in results) == [False, True]
    waiter = next(result for result in results if not result.produced)
    assert waiter.cached_public_bytes is not None
    assert json.loads(_loaded(waiter.cached_public_bytes)) == json.loads(public_bytes())


def test_live_owner_waiter_exhausts_deadline_without_starting_duplicate(tmp_path, monkeypatch):
    cache = _single_flight_cache(tmp_path, monkeypatch)
    marker_context = context()
    token = cache._process_token(os.getpid())
    assert isinstance(token, str)
    assert cache._write_marker(
        {
            "generation": 1,
            "owner_pid": os.getpid(),
            "owner_token": token,
            "started_at": "2026-08-15T00:00:00.000000Z",
        },
        marker_context,
    )
    fake_now = [0]
    sleeps = []
    monkeypatch.setattr(cache, "_sleep", lambda seconds: (sleeps.append(seconds), fake_now.__setitem__(0, fake_now[0] + int(seconds * 1_000_000_000))))
    deadline = DeadlineContext.from_seconds(0.05, t0_ns=0, clock_ns=lambda: fake_now[0])
    calls = []

    result = cache.get_or_refresh(deadline, lambda _: calls.append("duplicate"))

    assert result.deadline_exhausted
    assert calls == []
    assert sleeps


def test_dead_or_mismatched_owner_is_reclaimed_with_next_generation(tmp_path, monkeypatch):
    cache = _single_flight_cache(tmp_path, monkeypatch)
    assert cache._write_marker(
        {
            "generation": 7,
            "owner_pid": os.getpid(),
            "owner_token": "not-the-current-process",
            "started_at": "2026-08-15T00:00:00.000000Z",
        },
        context(),
    )

    result = cache.get_or_refresh(context(), lambda _: SingleFlightResult(value="fresh", produced=True))
    marker = cache._read_marker(context())

    assert result.value == "fresh"
    assert marker is not None
    assert marker["generation"] == 8
    assert marker["owner_pid"] == 0
    assert marker["owner_token"] == ""


def test_stale_generation_cannot_publish_after_authority_is_lost(tmp_path, monkeypatch):
    cache = _single_flight_cache(tmp_path, monkeypatch)
    current_token = cache._process_token(os.getpid())

    def producer(_):
        assert cache._write_marker(
            {
                "generation": 2,
                "owner_pid": os.getpid(),
                "owner_token": "new-authority",
                "started_at": "2026-08-15T00:00:00.000000Z",
            },
            context(),
        )
        return SingleFlightResult(value="stale", cached_public_bytes=public_bytes(), produced=True)

    result = cache.get_or_refresh(context(), producer)

    assert current_token
    assert result.value == "stale"
    assert result.cached_public_bytes is None
    assert cache.load(context()) is None
    marker = cache._read_marker(context())
    assert marker is not None and marker["generation"] == 2 and marker["owner_token"] == "new-authority"


def test_failed_publication_cleans_active_marker_without_cache_data(tmp_path, monkeypatch):
    cache = _single_flight_cache(tmp_path, monkeypatch)
    result = cache.get_or_refresh(context(), lambda _: SingleFlightResult(value="failed", cached_public_bytes=b"{}", produced=True))

    marker = cache._read_marker(context())
    assert result.value == "failed"
    assert result.cached_public_bytes is None
    assert marker is not None and marker["owner_pid"] == 0
    assert cache.load(context()) is None


def test_retry_claims_use_fresh_process_tokens(tmp_path, monkeypatch):
    cache = _single_flight_cache(tmp_path, monkeypatch)
    tokens = iter(("first-token", "second-token"))
    monkeypatch.setattr(cache, "_process_token", lambda _pid: next(tokens))
    calls = []

    def producer(_):
        calls.append(True)
        return SingleFlightResult(value=len(calls), cached_public_bytes=b"invalid", produced=True)

    assert cache.get_or_refresh(context(), producer).value == 1
    assert cache.get_or_refresh(context(), producer).value == 2
    assert calls == [True, True]


def test_owner_state_distinguishes_alive_dead_and_unknown_without_reclaiming_unknown(tmp_path, monkeypatch):
    from yasb_limitora import v2_cache

    cache = _single_flight_cache(tmp_path, monkeypatch)
    marker = {
        "generation": 1,
        "owner_pid": os.getpid(),
        "owner_token": "current",
        "started_at": "2026-08-15T00:00:00.000000Z",
    }
    monkeypatch.setattr(cache, "_process_token", lambda _pid: "current")
    assert cache._owner_state(marker) is OwnerState.ALIVE
    monkeypatch.setattr(cache, "_process_token", lambda _pid: v2_cache._PROCESS_MISSING)
    assert cache._owner_state(marker) is OwnerState.DEAD
    monkeypatch.setattr(cache, "_process_token", lambda _pid: (_ for _ in ()).throw(OSError("identity unreadable")))
    assert cache._owner_state(marker) is OwnerState.UNKNOWN

    assert cache._write_marker(marker, context())
    monkeypatch.setattr(cache, "_owner_state", lambda _marker: OwnerState.UNKNOWN)
    calls = []
    result = cache.get_or_refresh(context(), lambda _: calls.append(True))
    current = cache._read_marker(context())
    assert calls == [] and result.coordination_failed
    assert current is not None and current["generation"] == 1 and current["owner_pid"] == os.getpid()


def test_process_identity_distinguishes_definite_missing_from_unknown(monkeypatch):
    from yasb_limitora import v2_cache

    monkeypatch.setattr(v2_cache.os, "name", "posix")

    def raise_missing(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("builtins.open", raise_missing)
    assert v2_cache._process_creation_token(999999) is v2_cache._PROCESS_MISSING

    def raise_unknown(*args, **kwargs):
        raise PermissionError

    monkeypatch.setattr("builtins.open", raise_unknown)
    assert v2_cache._process_creation_token(999999) is None


def test_process_identity_query_failure_is_unknown_and_never_reclaimed(tmp_path, monkeypatch):
    cache = _single_flight_cache(tmp_path, monkeypatch)
    marker = {
        "generation": 3,
        "owner_pid": os.getpid(),
        "owner_token": "owner-token",
        "started_at": "2026-08-15T00:00:00.000000Z",
    }
    monkeypatch.setattr(cache, "_process_token", lambda _pid: None)

    assert cache._owner_state(marker) is OwnerState.UNKNOWN
    assert cache._write_marker(marker, context())
    calls = []
    result = cache.get_or_refresh(context(), lambda _: calls.append(True))

    assert calls == []
    assert result.coordination_failed
    current = cache._read_marker(context())
    assert current is not None and current["generation"] == 3 and current["owner_token"] == "owner-token"


def test_unreadable_marker_fails_closed_without_starting_a_second_producer(tmp_path, monkeypatch):
    cache = _single_flight_cache(tmp_path, monkeypatch)
    monkeypatch.setattr(cache, "_read_marker_state", lambda context: (None, False))
    calls = []

    result = cache.get_or_refresh(context(), lambda _: calls.append(True))

    assert calls == []
    assert result.coordination_failed
    assert result.coordination_error == "internal_error"


@pytest.mark.parametrize("error_code", ("guard_acquisition_failed", "guard_wait_timeout"))
def test_coordination_failure_never_runs_an_uncoordinated_producer(tmp_path, error_code, monkeypatch):
    cache, _ = make_cache(tmp_path)
    monkeypatch.setattr(cache, "_guard_factory", lambda: (_ for _ in ()).throw(GuardError(error_code)))
    calls = []

    result = cache.get_or_refresh(context(), lambda _: calls.append(True))

    assert calls == []
    assert result.coordination_failed
    assert result.coordination_error == error_code


def test_fresh_cache_hit_precedes_guard_failure_and_skips_producer(tmp_path, monkeypatch):
    cache, _ = make_cache(tmp_path)
    cached = public_bytes()
    assert cache.publish(cached, context())
    monkeypatch.setattr(cache, "_guard_factory", lambda: (_ for _ in ()).throw(GuardError("guard_acquisition_failed")))
    calls = []

    result = cache.get_or_refresh(context(), lambda _: calls.append(True))

    assert result.cached_public_bytes is not None and json.loads(_loaded(result.cached_public_bytes)) == json.loads(cached)
    assert not result.coordination_failed
    assert calls == []


@pytest.mark.parametrize("state", ("fresh", "absent", "corrupt", "expired"))
def test_guard_wait_timeout_does_one_final_uncoordinated_cache_read(tmp_path, state, monkeypatch):
    now = [datetime(2026, 8, 15, tzinfo=timezone.utc)]
    cache, _ = make_cache(tmp_path, now=lambda: now[0])
    cached = public_bytes()

    def publish_before_timeout():
        if state == "fresh":
            assert cache.publish(cached, context())
        elif state == "corrupt":
            assert cache.publish(cached, context())
            Path(cache.path).write_bytes(b"{")
        elif state == "expired":
            assert cache.publish(cached, context())
            now[0] += timedelta(seconds=CACHE_TTL_SECONDS + 1)

    class _TimeoutGuard:
        def acquire_key(self, key: bytes, deadline: DeadlineContext) -> _KeyLease:
            publish_before_timeout()
            raise GuardError("guard_wait_timeout")

    monkeypatch.setattr(cache, "_guard_factory", _TimeoutGuard)
    calls = []
    result = cache.get_or_refresh(context(), lambda _: calls.append(True))

    assert calls == []
    if state == "fresh":
        assert result.cached_public_bytes is not None
        assert json.loads(_loaded(result.cached_public_bytes)) == json.loads(cached)
        assert not result.coordination_failed
    else:
        assert result.coordination_failed
        assert result.coordination_error == "guard_wait_timeout"


def test_single_flight_deadline_exhaustion_does_not_start_provider(tmp_path, monkeypatch):
    cache = _single_flight_cache(tmp_path, monkeypatch)
    monkeypatch.setattr(cache, "_guard_factory", lambda: (_ for _ in ()).throw(GuardError("guard_wait_timeout")))
    expired = DeadlineContext(t0_ns=0, deadline_ns=0, reserve_ns=0, clock_ns=lambda: 0)
    calls = []

    result = cache.get_or_refresh(expired, lambda _: calls.append(True))

    assert result.deadline_exhausted
    assert calls == []
