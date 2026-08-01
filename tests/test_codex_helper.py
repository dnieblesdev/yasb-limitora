from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import limitora
import pytest
from limitora.models import Quantity, ProviderId, ProviderStatus, QuotaWindow, SourceMetadata, ValueAvailability, WindowKind

from yasb_limitora.codex_helper import CodexHelperExecutor
from yasb_limitora.limitora_api import (
    CodexLimitoraAdapter,
    read_opencode_go,
)
from yasb_limitora.model import (
    ProviderKey,
    ProviderOutcome,
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
)


def _snapshot(
    state=limitora.ProviderState.AVAILABLE,
    freshness=limitora.Freshness.FRESH,
    *,
    provider="codex",
    source="test",
    windows=(),
    observed_at=None,
    fetched_at=None,
    data_at=None,
):
    now = datetime.now(timezone.utc)
    observed_at = now if observed_at is None else observed_at
    fetched_at = observed_at if fetched_at is None else fetched_at
    data_at = observed_at if data_at is None else data_at
    provider_id = ProviderId(provider)
    status = ProviderStatus(provider_id, state, observed_at)
    snapshot = limitora.ProviderSnapshot(
        provider_id, status, fetched_at, data_at, SourceMetadata(source), tuple(windows)
    )
    return limitora.StatusSnapshotResult(snapshot, freshness)


def test_adapter_uses_root_public_api_and_maps_success_unavailable_stale_and_error():
    provider_error = limitora.ProviderError(
        limitora.ProviderErrorKind.TRANSPORT,
        limitora.ProviderId("codex"),
        "safe provider failure",
        retryable=False,
    )
    results = iter((_snapshot(), _snapshot(state=limitora.ProviderState.UNAVAILABLE), _snapshot(freshness=limitora.Freshness.STALE), provider_error, TimeoutError("secret")))

    class Client:
        def read_status(self, request):
            result = next(results)
            if isinstance(result, BaseException):
                raise result
            return result

    clients = iter((Client(), Client(), Client(), Client(), Client()))
    adapter = CodexLimitoraAdapter(lambda config: next(clients))
    assert adapter.read(("C:\\codex.exe",)).outcome is ProviderOutcome.SNAPSHOT
    assert adapter.read(("C:\\codex.exe",)).outcome is ProviderOutcome.SNAPSHOT
    assert adapter.read(("C:\\codex.exe",)).outcome is ProviderOutcome.SNAPSHOT
    provider_error_view = adapter.read(("C:\\codex.exe",))
    timeout_view = adapter.read(("C:\\codex.exe",))
    assert provider_error_view.error.code is SafeErrorCode.PROVIDER_ERROR
    assert provider_error_view.outcome is ProviderOutcome.EXECUTION_ERROR
    assert timeout_view.error.code is SafeErrorCode.TIMEOUT
    view = read_opencode_go("private-workspace", {})
    assert view.state is ProviderState.UNAVAILABLE
    assert view.outcome is ProviderOutcome.NOT_RUN
    assert "private-workspace" not in repr(view)


def _quantity(value: str, metric=limitora.MetricKind.COMMERCIAL_QUOTA, unit="percentage_points"):
    return Quantity(Decimal(value), metric, unit)


def test_adapter_preserves_snapshot_state_freshness_windows_and_safe_sources():
    observed_at = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
    fetched_at = datetime(2026, 8, 1, 12, 1, tzinfo=timezone.utc)
    data_at = datetime(2026, 8, 1, 12, 0, 30, tzinfo=timezone.utc)
    reset_at = datetime(2026, 8, 1, 16, tzinfo=timezone.utc)
    windows = (
        QuotaWindow(
            WindowKind.COMMERCIAL_QUOTA,
            "account",
            "five_hour",
            "plus",
            ValueAvailability.KNOWN,
            SourceMetadata("codex-app-server-v2"),
            _quantity("100.00"),
            _quantity("25.00"),
            _quantity("75.00"),
            reset_at,
        ),
        QuotaWindow(
            WindowKind.COMMERCIAL_QUOTA,
            "account",
            "weekly",
            None,
            ValueAvailability.UNAVAILABLE,
            SourceMetadata("private-provider-detail"),
        ),
    )
    client = SimpleNamespace(read_status=lambda request: _snapshot(
        state=limitora.ProviderState.PARTIAL,
        source="codex-app-server-v2",
        windows=windows,
        observed_at=observed_at,
        fetched_at=fetched_at,
        data_at=data_at,
    ))

    view = CodexLimitoraAdapter(lambda config: client).read(("C:\\codex.exe",))

    assert view.outcome is ProviderOutcome.SNAPSHOT
    assert view.state is ProviderState.SUCCESS
    assert view.error is None
    assert view.snapshot is not None
    assert view.snapshot.public_state is PublicProviderState.PARTIAL
    assert view.snapshot.freshness.value == "fresh"
    assert (view.snapshot.status_observed_at, view.snapshot.fetched_at, view.snapshot.data_at) == (
        observed_at,
        fetched_at,
        data_at,
    )
    assert view.snapshot.source_id == "codex-app-server-v2"
    assert len(view.snapshot.windows) == 2
    known, unavailable = view.snapshot.windows
    assert (known.scope, known.period, known.plan_id, known.reset_at) == ("account", "five_hour", "plus", reset_at)
    assert str(known.limit.value) == "100"
    assert str(known.used.value) == "25"
    assert str(known.remaining.value) == "75"
    assert known.source_id == "codex-app-server-v2"
    assert unavailable.source_id is None
    assert "private-provider-detail" not in repr(view)


def test_adapter_retains_stale_and_empty_snapshots_as_snapshots():
    results = iter((
        _snapshot(state=limitora.ProviderState.AVAILABLE, freshness=limitora.Freshness.STALE),
        _snapshot(state=limitora.ProviderState.UNAVAILABLE, windows=()),
    ))
    client = SimpleNamespace(read_status=lambda request: next(results))
    adapter = CodexLimitoraAdapter(lambda config: client)

    stale = adapter.read(("C:\\codex.exe",))
    empty = adapter.read(("C:\\codex.exe",))

    assert stale.state is ProviderState.UNAVAILABLE
    assert stale.outcome is ProviderOutcome.SNAPSHOT
    assert stale.snapshot is not None and stale.snapshot.freshness.value == "stale"
    assert stale.snapshot.public_state is PublicProviderState.AVAILABLE
    assert empty.outcome is ProviderOutcome.SNAPSHOT
    assert empty.snapshot is not None and empty.snapshot.windows == ()
    assert empty.snapshot.public_state is PublicProviderState.UNAVAILABLE


def test_adapter_keeps_undetected_distinct_from_an_unavailable_snapshot():
    client = SimpleNamespace(read_status=lambda request: limitora.StatusUndetectedResult())

    view = CodexLimitoraAdapter(lambda config: client).read(("C:\\codex.exe",))

    assert view.state is ProviderState.UNAVAILABLE
    assert view.outcome is ProviderOutcome.UNDETECTED
    assert view.snapshot is None


def test_adapter_fails_closed_for_unknown_state_and_unsupported_metric():
    now = datetime.now(timezone.utc)
    unknown_status = ProviderStatus(ProviderId("codex"), "future_state", now)
    unknown_snapshot = limitora.ProviderSnapshot(
        ProviderId("codex"), unknown_status, now, now, SourceMetadata("test")
    )
    unsupported_window = QuotaWindow(
        WindowKind.OTHER,
        "account",
        "future",
        None,
        ValueAvailability.KNOWN,
        SourceMetadata("codex-app-server-v2"),
        _quantity("10", limitora.MetricKind.TOKENS, "tokens"),
    )
    invalid_snapshot = _snapshot(windows=(unsupported_window,)).snapshot
    results = iter((
        limitora.StatusSnapshotResult(unknown_snapshot, limitora.Freshness.FRESH),
        limitora.StatusSnapshotResult(invalid_snapshot, limitora.Freshness.FRESH),
    ))
    client = SimpleNamespace(read_status=lambda request: next(results))
    adapter = CodexLimitoraAdapter(lambda config: client)

    unknown = adapter.read(("C:\\codex.exe",))
    invalid = adapter.read(("C:\\codex.exe",))

    assert unknown.outcome is ProviderOutcome.EXECUTION_ERROR
    assert unknown.error.code is SafeErrorCode.UNKNOWN_PROVIDER_STATE
    assert unknown.snapshot is None
    assert invalid.outcome is ProviderOutcome.EXECUTION_ERROR
    assert invalid.error.code is SafeErrorCode.INVALID_PROVIDER_DATA
    assert invalid.snapshot is None


@pytest.mark.parametrize(
    ("state", "legacy_state"),
    (
        (limitora.ProviderState.PARTIAL, ProviderState.SUCCESS),
        (limitora.ProviderState.UNAUTHORIZED, ProviderState.UNAVAILABLE),
        (limitora.ProviderState.RATE_LIMITED, ProviderState.UNAVAILABLE),
        (limitora.ProviderState.TRANSIENT_ERROR, ProviderState.UNAVAILABLE),
        (limitora.ProviderState.INVALID_DATA, ProviderState.UNAVAILABLE),
    ),
)
def test_valid_non_available_public_states_remain_snapshot_outcomes(state, legacy_state):
    result = _snapshot(state=state)
    client = SimpleNamespace(read_status=lambda request: result)

    view = CodexLimitoraAdapter(lambda config: client).read(("C:\\codex.exe",))

    assert view.state is legacy_state
    assert view.error is None
    assert view.outcome is ProviderOutcome.SNAPSHOT
    assert view.snapshot is not None
    assert view.snapshot.public_state.value == state.value


def test_provider_view_rejects_snapshot_error_contradictions_but_keeps_other_outcomes_legal():
    valid = _snapshot()
    client = SimpleNamespace(read_status=lambda request: valid)
    snapshot = CodexLimitoraAdapter(lambda config: client).read(("C:\\codex.exe",)).snapshot
    assert snapshot is not None

    with pytest.raises(ValueError, match="snapshot cannot carry"):
        ProviderView(
            ProviderKey.CODEX,
            ProviderState.SAFE_ERROR,
            SafeError(SafeErrorCode.PROVIDER_ERROR),
            outcome=ProviderOutcome.SNAPSHOT,
            snapshot=snapshot,
        )
    with pytest.raises(ValueError, match="only safe_error"):
        ProviderView(
            ProviderKey.CODEX,
            ProviderState.SUCCESS,
            SafeError(SafeErrorCode.PROVIDER_ERROR),
            outcome=ProviderOutcome.SNAPSHOT,
            snapshot=snapshot,
        )

    execution_error = ProviderView(
        ProviderKey.CODEX,
        ProviderState.SAFE_ERROR,
        SafeError(SafeErrorCode.PROVIDER_ERROR),
        outcome=ProviderOutcome.EXECUTION_ERROR,
    )
    not_run = ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.NOT_RUN)
    assert execution_error.outcome is ProviderOutcome.EXECUTION_ERROR
    assert not_run.outcome is ProviderOutcome.NOT_RUN


def test_model_and_adapter_share_nfc_identity_normalization():
    decomposed = "cafe\u0301"
    normalized = "café"
    direct_quantity = QuotaQuantity(Decimal("1"), QuotaMetricKind.COMMERCIAL_QUOTA, decomposed)
    direct_window = QuotaWindowView(
        QuotaWindowKind.COMMERCIAL_QUOTA,
        decomposed,
        decomposed,
        decomposed,
        QuotaAvailability.KNOWN,
        None,
        limit=direct_quantity,
    )
    assert direct_quantity.unit == normalized
    assert (direct_window.scope, direct_window.period, direct_window.plan_id) == (
        normalized,
        normalized,
        normalized,
    )

    public_window = QuotaWindow(
        WindowKind.COMMERCIAL_QUOTA,
        decomposed,
        decomposed,
        decomposed,
        ValueAvailability.KNOWN,
        SourceMetadata("test"),
        _quantity("1", unit=decomposed),
    )
    result = _snapshot(windows=(public_window,))
    client = SimpleNamespace(read_status=lambda request: result)
    view = CodexLimitoraAdapter(lambda config: client).read(("C:\\codex.exe",))

    assert view.snapshot is not None
    adapter_window = view.snapshot.windows[0]
    assert (adapter_window.scope, adapter_window.period, adapter_window.plan_id) == (
        normalized,
        normalized,
        normalized,
    )
    assert adapter_window.limit.unit == normalized


def _read_single_quantity(raw: str):
    window = QuotaWindow(
        WindowKind.COMMERCIAL_QUOTA,
        "account",
        "five_hour",
        "plus",
        ValueAvailability.KNOWN,
        SourceMetadata("test"),
        _quantity(raw),
    )
    result = _snapshot(windows=(window,))
    client = SimpleNamespace(read_status=lambda request: result)
    return CodexLimitoraAdapter(lambda config: client).read(("C:\\codex.exe",))


def test_adapter_uses_fixed_point_canonical_quantities_and_normalizes_negative_zero():
    window = QuotaWindow(
        WindowKind.COMMERCIAL_QUOTA,
        "account",
        "five_hour",
        "plus",
        ValueAvailability.KNOWN,
        SourceMetadata("test"),
        _quantity("1E+2"),
        _quantity("-0"),
    )
    result = _snapshot(windows=(window,))
    client = SimpleNamespace(read_status=lambda request: result)

    view = CodexLimitoraAdapter(lambda config: client).read(("C:\\codex.exe",))

    assert view.snapshot is not None
    limit, used = view.snapshot.windows[0].limit, view.snapshot.windows[0].used
    assert str(limit.value) == "100"
    assert str(used.value) == "0"
    assert not used.value.is_signed()


def test_model_accepts_positive_exponent_place_value_zeroes_but_rejects_over_256_rendering():
    accepted = QuotaQuantity(Decimal("1E+200"), QuotaMetricKind.COMMERCIAL_QUOTA, "units")

    assert str(accepted.value) == "1" + "0" * 200
    assert len(format(accepted.value, "f")) == 201
    with pytest.raises(ValueError, match="canonical limits"):
        QuotaQuantity(Decimal("1E+256"), QuotaMetricKind.COMMERCIAL_QUOTA, "units")


def test_adapter_preserves_positive_exponent_quantity_and_rejects_over_256_rendering():
    accepted = _read_single_quantity("1E+200")
    rejected = _read_single_quantity("1E+256")

    assert accepted.outcome is ProviderOutcome.SNAPSHOT
    assert accepted.snapshot is not None
    assert str(accepted.snapshot.windows[0].limit.value) == "1" + "0" * 200
    assert rejected.outcome is ProviderOutcome.EXECUTION_ERROR
    assert rejected.error.code is SafeErrorCode.INVALID_PROVIDER_DATA
    assert rejected.snapshot is None


@pytest.mark.parametrize(
    ("raw", "rendered_length"),
    (("9" * 128, 128), ("0." + "0" * 126 + "9" * 128, 256)),
)
def test_adapter_accepts_quantity_boundary_limits(raw, rendered_length):
    view = _read_single_quantity(raw)

    assert view.outcome is ProviderOutcome.SNAPSHOT
    assert view.snapshot is not None
    rendered = format(view.snapshot.windows[0].limit.value, "f")
    assert "E" not in rendered and len(rendered) == rendered_length


@pytest.mark.parametrize("raw", ("9" * 129, "0." + "0" * 127 + "9" * 128))
def test_adapter_rejects_quantity_values_over_normative_limits(raw):
    view = _read_single_quantity(raw)

    assert view.outcome is ProviderOutcome.EXECUTION_ERROR
    assert view.error.code is SafeErrorCode.INVALID_PROVIDER_DATA
    assert view.snapshot is None


def test_concurrent_cleanup_ownership_is_atomic():
    import threading
    started, release, created, fail = threading.Event(), threading.Event(), [], [True]
    def close(timeout):
        if fail[0]: raise RuntimeError("private cleanup detail")
    def factory(**kwargs):
        created.append(1)
        return SimpleNamespace(acquire=lambda: (started.set(), release.wait()), close=close)
    executor = CodexHelperExecutor(factory)
    barrier, results = threading.Barrier(2), [None, None]
    def work(index): barrier.wait(); results.__setitem__(index, executor.run(("C:\\codex.exe",)))
    threads = [threading.Thread(target=work, args=(index,)) for index in range(2)]
    [thread.start() for thread in threads]; started.wait(); release.set(); [thread.join() for thread in threads]
    assert len(created) == 1 and all(result.error.code is SafeErrorCode.INTERNAL_ERROR for result in results)
    assert executor.retry_cleanup() is False; fail[0] = False
    assert executor.retry_cleanup() and executor.run(("C:\\codex.exe",)).error.code is SafeErrorCode.PROVIDER_ERROR and len(created) == 2


def test_ready_trailing_data_fails_before_dispatch():
    from yasb_limitora.codex_helper import _PersistentTransport, _TransportError
    peeks = iter(((7, False), (4, False)))
    transport = _PersistentTransport(1, 2, peek=lambda fd: next(peeks), read=lambda fd, size: b"READY:n", nonblocking=True)
    rejected = []
    def acquire():
        try: transport.read_frame(expected_size=7)
        except _TransportError: rejected.append(True); raise
        raise AssertionError("trailing READY was accepted")
    supervisor = SimpleNamespace(acquire=acquire, close=lambda timeout: None)
    result = CodexHelperExecutor(lambda **kwargs: supervisor).run(("C:\\codex.exe",))
    assert result.error.code is SafeErrorCode.PROVIDER_ERROR
    assert rejected == [True]
