from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import io
import json
import os
import struct
import sys
from types import SimpleNamespace

import limitora
import pytest
from limitora.models import Quantity, ProviderId, ProviderStatus, QuotaWindow, SourceMetadata, ValueAvailability, WindowKind

import yasb_limitora.cli as cli
import yasb_limitora.codex_helper as codex_helper
from yasb_limitora.codex_helper import CodexHelperExecutor, _CHILD_BOOTSTRAP, _decode, _decode_timestamp, _INTERNAL_HELPER_FLAG, _payload, _source_for_provider, _timestamp
from yasb_limitora.deadline import DeadlineContext
from yasb_limitora.limitora_api import (
    CodexLimitoraAdapter,
    OpenCodeRequest,
    read_opencode_go,
)
from yasb_limitora.model import (
    MAX_DISPLAY_LABEL_LENGTH,
    _legacy_state_for_snapshot,
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
    ProviderSnapshotView,
    SnapshotFreshness,
)


def test_frozen_runtime_uses_private_internal_helper_flag(monkeypatch):
    import yasb_limitora.codex_helper as helper

    monkeypatch.setattr(helper.sys, "frozen", True, raising=False)
    assert helper._helper_command() == (helper.sys.executable, helper._INTERNAL_HELPER_FLAG)


def test_internal_helper_mode_runs_authenticated_pipe_handshake(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(codex_helper.os, "name", "nt")
    gate_read, gate_write = os.pipe()
    data_read, data_write = os.pipe()
    expected = ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.UNDETECTED)
    request = json.dumps({"runner": ["codex"], "nonce": "ready-nonce"}, separators=(",", ":")).encode()
    os.write(gate_write, b"1" + struct.pack(">I", len(request)) + request)
    os.close(gate_write)
    native_gate, native_data = 0x1234, 0x5678

    def open_osfhandle(handle, flags):
        return {native_gate: gate_read, native_data: data_write}[handle]

    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(open_osfhandle=open_osfhandle))
    monkeypatch.setenv("_YASB_CODEX_GATE_HANDLE", str(native_gate))
    monkeypatch.setenv("_YASB_CODEX_DATA_HANDLE", str(native_data))
    monkeypatch.setenv("_YASB_CODEX_READY_NONCE", "ready-nonce")
    calls = []
    monkeypatch.setattr("yasb_limitora.limitora_api.read_codex", lambda runner: calls.append(runner) or expected)
    stdout, stderr = io.BytesIO(), io.StringIO()

    try:
        assert cli.main([_INTERNAL_HELPER_FLAG], stdout=stdout, stderr=stderr, platform_is_windows=lambda: True) == 0
        assert os.read(data_read, len(b"READY:ready-nonce")) == b"READY:ready-nonce"
        size = struct.unpack(">I", os.read(data_read, 4))[0]
        assert codex_helper._decode(os.read(data_read, size)) == expected
    finally:
        os.close(data_read)

    assert calls == [["codex"]]
    assert stdout.getvalue() == b"" and stderr.getvalue() == ""


def test_non_frozen_helper_command_keeps_isolated_bootstrap(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    assert codex_helper._helper_command() == (sys.executable, "-I", "-E", "-c", _CHILD_BOOTSTRAP)


def _snapshot(
    state=limitora.ProviderState.AVAILABLE,
    freshness=limitora.Freshness.FRESH,
    *,
    provider="codex",
    source="codex-app-server-v2",
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
    view = read_opencode_go(OpenCodeRequest("private-api-key", 7)).view
    assert view.state is ProviderState.SAFE_ERROR
    assert view.error is not None and view.error.code is SafeErrorCode.PROVIDER_ERROR
    assert "private-api-key" not in repr(view)


def test_prestart_deadline_exhaustion_marks_codex_not_run_without_spawning():
    expired = DeadlineContext(t0_ns=0, deadline_ns=0, reserve_ns=0, clock_ns=lambda: 0)
    executor = CodexHelperExecutor(lambda **kwargs: (_ for _ in ()).throw(AssertionError("provider spawned")))

    result = executor.run_with_deadline(("C:\\codex.exe",), expired)

    assert result.outcome is ProviderOutcome.NOT_RUN
    assert result.not_run_reason == "deadline_exhausted"


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


@pytest.mark.parametrize("source,outcome", ((SourceMetadata("future-source"), ProviderOutcome.SNAPSHOT), (None, ProviderOutcome.EXECUTION_ERROR), (object(), ProviderOutcome.EXECUTION_ERROR)))
def test_adapter_requires_source_metadata_and_normalizes_unknown_source(source, outcome):
    result = _snapshot(); object.__setattr__(result.snapshot, "source", source)
    view = CodexLimitoraAdapter(lambda config: SimpleNamespace(read_status=lambda request: result)).read(("C:\\codex.exe",))
    assert view.outcome is outcome
    assert (view.snapshot.source_id if view.snapshot is not None else view.error.code) is (None if outcome is ProviderOutcome.SNAPSHOT else SafeErrorCode.INVALID_PROVIDER_DATA)


def test_opencode_adapter_uses_keyword_bearer_api_and_emits_provider_source(monkeypatch):
    observed_at = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
    window = QuotaWindow(WindowKind.COMMERCIAL_QUOTA, "account", "weekly", None, ValueAvailability.KNOWN, SourceMetadata("opencode-go-api"), _quantity("100"), _quantity("25"), _quantity("75"), observed_at)
    client = SimpleNamespace(read_status=lambda request: _snapshot(provider="opencode-go", source="opencode-go-api", windows=(window,), observed_at=observed_at, fetched_at=observed_at, data_at=observed_at))
    captured = []
    monkeypatch.setattr("yasb_limitora.limitora_api.activate_provider", lambda config: (captured.append(config) or client))
    result = read_opencode_go(OpenCodeRequest("bearer-sentinel", 7.0))
    assert (captured[0].api_key, captured[0].timeout) == ("bearer-sentinel", timedelta(seconds=7))
    assert result.view.snapshot is not None
    weekly = next(window for window in result.view.snapshot.windows if window.period == "weekly")
    assert (result.view.snapshot.source_id, weekly.source_id) == ("opencode-go-api",) * 2
    assert "bearer-sentinel" not in repr(result)


def _malformed_window(source, **mutations):
    observed_at = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
    window = QuotaWindow(
        WindowKind.COMMERCIAL_QUOTA, "account", "weekly", "plus", ValueAvailability.KNOWN,
        SourceMetadata(source), _quantity("100"), _quantity("25"), _quantity("75"), observed_at,
    )
    for field, value in mutations.items(): object.__setattr__(window, field, value)
    return window


@pytest.mark.parametrize(
    ("source", "mutations", "expected_outcome"),
    (
        ("future-source", {"availability": "malformed", "plan_id": object(), "limit": object(), "used": object(), "remaining": object(), "reset_at": object()}, ProviderOutcome.SNAPSHOT),
        ("codex-app-server-v2", {"availability": "malformed", "plan_id": object(), "limit": object(), "used": object(), "remaining": object(), "reset_at": object()}, ProviderOutcome.SNAPSHOT),
    ),
)
def test_adapter_trusts_only_provider_bound_window_evidence(monkeypatch, source, mutations, expected_outcome):
    monkeypatch.setattr("yasb_limitora.limitora_api.activate_provider", lambda config: SimpleNamespace(
        read_status=lambda request: _snapshot(
            provider="opencode-go", source="opencode-go-api", windows=(_malformed_window(source, **mutations),)
        )
    ))
    result = read_opencode_go(OpenCodeRequest("bearer-sentinel", 7.0)).view

    assert result.outcome is expected_outcome
    if expected_outcome is ProviderOutcome.SNAPSHOT:
        assert result.snapshot is not None
        normalized = result.snapshot.windows[0]
        assert normalized.source_id is None
        assert normalized.availability is QuotaAvailability.UNAVAILABLE
        assert all(getattr(normalized, field) is None for field in ("plan_id", "limit", "used", "remaining", "reset_at"))
    else:
        assert result.error is not None and result.error.code is SafeErrorCode.INVALID_PROVIDER_DATA


@pytest.mark.parametrize("field", ("availability", "plan_id", "limit", "used", "remaining", "reset_at", "period", "scope"))
def test_adapter_rejects_malformed_trusted_window_fields(monkeypatch, field):
    monkeypatch.setattr("yasb_limitora.limitora_api.activate_provider", lambda config: SimpleNamespace(
        read_status=lambda request: _snapshot(
            provider="opencode-go", source="opencode-go-api", windows=(_malformed_window("opencode-go-api", **{field: object()}),)
        )
    ))

    result = read_opencode_go(OpenCodeRequest("bearer-sentinel", 7.0)).view

    assert result.outcome is ProviderOutcome.EXECUTION_ERROR
    assert result.error is not None and result.error.code is SafeErrorCode.INVALID_PROVIDER_DATA


@pytest.mark.parametrize("kind,message,evidence", ((limitora.ProviderErrorKind.UNAUTHORIZED, "invalid bearer", "credential_invalid"), (limitora.ProviderErrorKind.RATE_LIMITED, "provider busy", "rate_limited"), (limitora.ProviderErrorKind.TRANSPORT, "OpenCode Go request timed out", "timeout"), (limitora.ProviderErrorKind.SOURCE_UNAVAILABLE, "provider unavailable", "unavailable")))
def test_opencode_adapter_maps_released_errors_to_private_evidence_without_new_public_codes(monkeypatch, kind, message, evidence):
    failure = limitora.ProviderError(
        kind,
        limitora.ProviderId("opencode-go"),
        message,
        retryable=True,
    )
    client = SimpleNamespace(read_status=lambda request: (_ for _ in ()).throw(failure))
    monkeypatch.setattr("yasb_limitora.limitora_api.activate_provider", lambda config: client)
    result = read_opencode_go(OpenCodeRequest("bearer-sentinel", 7.0))
    assert result.view.error is not None
    assert result.view.error.code is (
        SafeErrorCode.TIMEOUT
        if evidence == "timeout"
        else SafeErrorCode.PROVIDER_ERROR
    )
    assert result.evidence.value == evidence and message not in repr(result)
    assert "bearer-sentinel" not in repr(result)


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


def _rich_view(*, freshness=SnapshotFreshness.FRESH, public_state=PublicProviderState.PARTIAL):
    observed_at = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    fetched_at = datetime(2026, 8, 1, 12, 1, 2, 345678, tzinfo=timezone.utc)
    data_at = datetime(2026, 8, 1, 12, 0, 30, tzinfo=timezone.utc)
    known = QuotaWindowView(
        QuotaWindowKind.COMMERCIAL_QUOTA,
        "account",
        "five_hour",
        "plus",
        QuotaAvailability.KNOWN,
        "codex-app-server-v2",
        limit=QuotaQuantity(Decimal("100"), QuotaMetricKind.COMMERCIAL_QUOTA, "percentage_points"),
        used=QuotaQuantity(Decimal("25"), QuotaMetricKind.COMMERCIAL_QUOTA, "percentage_points"),
        remaining=QuotaQuantity(Decimal("75"), QuotaMetricKind.COMMERCIAL_QUOTA, "percentage_points"),
        reset_at=datetime(2026, 8, 1, 16, tzinfo=timezone.utc),
    )
    unavailable = QuotaWindowView(
        QuotaWindowKind.COMMERCIAL_QUOTA,
        "account",
        "weekly",
        None,
        QuotaAvailability.UNAVAILABLE,
        None,
    )
    snapshot = ProviderSnapshotView(
        public_state,
        freshness,
        observed_at,
        fetched_at,
        data_at,
        "codex-app-server-v2",
        (known, unavailable),
    )
    return ProviderView(
        ProviderKey.CODEX,
        _legacy_state_for_snapshot(snapshot),
        display_label="Quota café 日本",
        outcome=ProviderOutcome.SNAPSHOT,
        snapshot=snapshot,
    )


def test_rich_private_payload_round_trips_all_snapshot_dimensions_without_float_conversion():
    view = _rich_view(freshness=SnapshotFreshness.STALE)

    payload = _payload(view)
    decoded = _decode(payload)

    assert decoded == view
    assert "Quota café 日本".encode("utf-8") in payload
    assert b'"value":"100"' in payload
    assert b"e+" not in payload.lower()
    assert decoded.snapshot is not None
    assert decoded.snapshot.windows[0].limit.value == Decimal("100")
    assert decoded.snapshot.windows[0].reset_at == datetime(2026, 8, 1, 16, tzinfo=timezone.utc)


def test_wire_label_and_timestamp_limits_are_named_and_enforced_at_boundaries():
    source = _rich_view()
    bounded = ProviderView(
        ProviderKey.CODEX,
        source.state,
        display_label="x" * MAX_DISPLAY_LABEL_LENGTH,
        outcome=source.outcome,
        snapshot=source.snapshot,
    )

    assert _decode(_payload(bounded)) == bounded
    oversized = json.loads(_payload(bounded).decode("utf-8"))
    oversized["display_label"] += "x"
    rejected = _decode(json.dumps(oversized, separators=(",", ":")).encode("utf-8"))
    assert rejected.error.code is SafeErrorCode.INTERNAL_ERROR


def test_rich_timestamps_normalize_equal_offset_instants_to_identical_canonical_bytes():
    source = _rich_view()
    offset = timezone(timedelta(hours=2))
    snapshot = source.snapshot
    assert snapshot is not None
    shifted_window = replace(
        snapshot.windows[0],
        reset_at=datetime(2026, 8, 1, 18, tzinfo=offset),
    )
    shifted_snapshot = replace(
        snapshot,
        status_observed_at=datetime(2026, 8, 1, 14, tzinfo=offset),
        fetched_at=datetime(2026, 8, 1, 14, 1, 2, 345678, tzinfo=offset),
        data_at=datetime(2026, 8, 1, 14, 0, 30, tzinfo=offset),
        windows=(shifted_window, snapshot.windows[1]),
    )
    shifted = replace(source, snapshot=shifted_snapshot)

    assert _timestamp(datetime(2026, 8, 1, 14, 1, 2, 345678, tzinfo=offset)) == (
        "2026-08-01T12:01:02.345678Z"
    )
    assert _payload(shifted) == _payload(source)
    assert _decode_timestamp("2026-08-01T12:01:02.345678Z") == datetime(
        2026, 8, 1, 12, 1, 2, 345678, tzinfo=timezone.utc
    )


@pytest.mark.parametrize(
    "wire",
    (
        "2026-08-01T12:01:02.345678+00:00",
        "2026-08-01T12:01:02.123Z",
        "2026-08-01T12:01:02.345678",
        "2026-08-01T12:01:02.3456787Z",
        "2026-02-30T12:01:02.345678Z",
    ),
)
def test_decoder_rejects_noncanonical_or_malformed_timestamp_wire_forms(wire):
    with pytest.raises(ValueError, match="invalid timestamp"):
        _decode_timestamp(wire)


def test_executor_returns_the_rich_child_result_after_authenticated_dispatch(monkeypatch):
    expected = _rich_view()
    writes = []

    class Transport:
        def write_control(self, payload, *, timeout_seconds):
            writes.append(payload)

        def read_response(self, timeout_seconds):
            return _payload(expected)

    monkeypatch.setattr("yasb_limitora.codex_helper._PersistentTransport", lambda *args, **kwargs: Transport())

    def factory(**kwargs):
        kwargs["transport_factory"](1, 2, nonblocking=True)
        return SimpleNamespace(_nonce=b"nonce", acquire=lambda: None, close=lambda timeout: None)

    result = CodexHelperExecutor(factory).run(("C:\\codex.exe",))

    assert result == expected
    assert b'"nonce":"nonce"' in writes[0]


def test_executor_preserves_decoded_snapshot_when_supervisor_cleanup_fails(monkeypatch):
    expected = _rich_view()

    class Transport:
        def write_control(self, payload, *, timeout_seconds):
            pass

        def read_response(self, timeout_seconds):
            return _payload(expected)

    monkeypatch.setattr("yasb_limitora.codex_helper._PersistentTransport", lambda *args, **kwargs: Transport())

    def factory(**kwargs):
        kwargs["transport_factory"](1, 2, nonblocking=True)

        def close(timeout):
            raise RuntimeError("private cleanup detail")

        return SimpleNamespace(_nonce=b"nonce", acquire=lambda: None, close=close)

    executor = CodexHelperExecutor(factory)
    assert executor.run((r"C:\codex.exe", "app-server")) == expected
    assert executor._pending_supervisor is not None


def test_deadline_executor_preserves_decoded_snapshot_when_cleanup_fails(monkeypatch):
    expected = _rich_view()

    class Transport:
        def write_control_with_deadline(self, payload, *, context):
            pass

        def read_response_with_deadline(self, context):
            return _payload(expected)

    monkeypatch.setattr("yasb_limitora.codex_helper._PersistentTransport", lambda *args, **kwargs: Transport())

    def factory(**kwargs):
        kwargs["transport_factory"](1, 2, nonblocking=True)

        def close_with_deadline(context):
            raise RuntimeError("private cleanup detail")

        return SimpleNamespace(
            _nonce=b"nonce",
            acquire_with_deadline=lambda context: None,
            close_with_deadline=close_with_deadline,
        )

    executor = CodexHelperExecutor(factory)
    result = executor.run_with_deadline((r"C:\codex.exe", "app-server"), DeadlineContext.from_seconds(1))
    assert result == expected
    assert executor._pending_supervisor is not None


@pytest.mark.parametrize(
    ("view", "state", "outcome"),
    (
        (_rich_view(), ProviderState.SUCCESS, ProviderOutcome.SNAPSHOT),
        (_rich_view(freshness=SnapshotFreshness.STALE), ProviderState.UNAVAILABLE, ProviderOutcome.SNAPSHOT),
        (_rich_view(public_state=PublicProviderState.UNAVAILABLE), ProviderState.UNAVAILABLE, ProviderOutcome.SNAPSHOT),
        (ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.UNDETECTED), ProviderState.UNAVAILABLE, ProviderOutcome.UNDETECTED),
        (ProviderView(ProviderKey.CODEX, ProviderState.SAFE_ERROR, SafeError(SafeErrorCode.PROVIDER_ERROR), outcome=ProviderOutcome.EXECUTION_ERROR), ProviderState.SAFE_ERROR, ProviderOutcome.EXECUTION_ERROR),
    ),
)
def test_rich_helper_round_trip_preserves_r3_outcome_mapping(view, state, outcome):
    decoded = _decode(_payload(view))

    assert decoded.state is state
    assert decoded.outcome is outcome
    assert decoded.snapshot == view.snapshot


@pytest.mark.parametrize("mutation", ("missing", "unknown", "enum", "naive", "quantity", "trusted_reset", "trusted_plan", "contradiction"))
def test_rich_decoder_rejects_malformed_or_contradictory_worker_output(mutation):
    value = json.loads(_payload(_rich_view()).decode("utf-8"))
    if mutation == "missing":
        del value["snapshot"]
    elif mutation == "unknown":
        value["unexpected"] = True
    elif mutation == "enum":
        value["state"] = "future"
    elif mutation == "naive":
        value["snapshot"]["fetched_at"] = "2026-08-01T12:01:02.345678"
    elif mutation == "quantity":
        value["snapshot"]["windows"][0]["limit"]["value"] = "1.00"
    elif mutation in ("trusted_reset", "trusted_plan"):
        value["snapshot"]["windows"][0]["reset_at"] = "not-a-timestamp" if mutation == "trusted_reset" else value["snapshot"]["windows"][0]["reset_at"]; value["snapshot"]["windows"][0]["plan_id"] = {"invalid": True} if mutation == "trusted_plan" else value["snapshot"]["windows"][0]["plan_id"]
    else:
        value["state"] = "safe_error"
        value["error"] = {"code": "provider_error"}
    decoded = _decode(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    assert decoded.state is ProviderState.SAFE_ERROR
    assert decoded.error.code is SafeErrorCode.INTERNAL_ERROR
    assert decoded.outcome is ProviderOutcome.EXECUTION_ERROR
    assert decoded.snapshot is None


@pytest.mark.parametrize(("root_source", "window_source", "trusted_window"), (("opencode-go-api", "opencode-go-api", False), ("future-source", "codex-app-server-v2", True)))
def test_rich_decoder_normalizes_sources_before_trusting_evidence(root_source, window_source, trusted_window):
    value = json.loads(_payload(_rich_view()).decode("utf-8"))
    value["snapshot"]["source_id"] = root_source
    value["snapshot"]["windows"][0]["source_id"] = window_source

    decoded = _decode(json.dumps(value, separators=(",", ":")).encode("utf-8"))

    assert decoded.outcome is ProviderOutcome.SNAPSHOT and decoded.snapshot is not None and decoded.snapshot.source_id is None
    window = decoded.snapshot.windows[0]
    if trusted_window:
        assert window.source_id == "codex-app-server-v2" and window.limit is not None
    else:
        assert window.source_id is None and window.availability is QuotaAvailability.UNAVAILABLE
        assert all(getattr(window, field) is None for field in ("plan_id", "limit", "used", "remaining", "reset_at"))


@pytest.mark.parametrize(("source", "expected"), ((" codex-app-server-v2 ", "codex-app-server-v2"), ("future-source", None), ("opencode-go-api", None), (None, None), (42, None)))
def test_provider_source_helper_normalizes_and_rejects_untrusted_values(source, expected):
    assert _source_for_provider(source, ProviderKey.CODEX) == expected


@pytest.mark.parametrize(
    ("source", "field", "value"),
    (
        ("future-source", "reset_at", "not-a-timestamp"),
        (
            "opencode-go-api",
            "limit",
            {"metric": "commercial_quota", "value": "not-a-decimal", "unit": "percentage_points"},
        ),
    ),
)
def test_rich_decoder_scrubs_untrusted_malformed_window_evidence(source, field, value):
    payload = json.loads(_payload(_rich_view()).decode("utf-8"))
    window = payload["snapshot"]["windows"][0]
    window["source_id"] = source
    window[field] = value
    if field == "reset_at": window["plan_id"] = {"invalid": True}

    decoded = _decode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    assert decoded.outcome is ProviderOutcome.SNAPSHOT
    assert decoded.snapshot is not None
    window = decoded.snapshot.windows[0]
    assert window.source_id is None
    assert window.availability is QuotaAvailability.UNAVAILABLE
    assert all(getattr(window, field) is None for field in ("plan_id", "limit", "used", "remaining", "reset_at"))


def test_rich_decoder_rejects_duplicate_fields_and_oversized_or_duplicate_windows():
    payload = _payload(_rich_view()).decode("utf-8").replace('"state":"success"', '"state":"success","state":"success"', 1)
    duplicate = _decode(payload.encode("utf-8"))
    assert duplicate.error.code is SafeErrorCode.INTERNAL_ERROR

    value = json.loads(_payload(_rich_view()).decode("utf-8"))
    value["snapshot"]["windows"] = value["snapshot"]["windows"] * 33
    oversized = _decode(json.dumps(value, separators=(",", ":")).encode("utf-8"))
    assert oversized.error.code is SafeErrorCode.INTERNAL_ERROR

    value = json.loads(_payload(_rich_view()).decode("utf-8"))
    value["snapshot"]["windows"].append(value["snapshot"]["windows"][0])
    duplicate_window = _decode(json.dumps(value, separators=(",", ":")).encode("utf-8"))
    assert duplicate_window.error.code is SafeErrorCode.INTERNAL_ERROR


def test_rich_decoder_rejects_snapshot_state_that_does_not_match_freshness_or_public_state():
    value = json.loads(_payload(_rich_view(freshness=SnapshotFreshness.STALE)).decode("utf-8"))
    value["state"] = "success"

    decoded = _decode(json.dumps(value, separators=(",", ":")).encode("utf-8"))

    assert decoded.error.code is SafeErrorCode.INTERNAL_ERROR


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
        SourceMetadata("codex-app-server-v2"),
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
        SourceMetadata("codex-app-server-v2"),
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
        SourceMetadata("codex-app-server-v2"),
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
    pending = executor._pending_supervisor
    assert pending is not None
    assert executor.run(("C:\\codex.exe",)).error.code is SafeErrorCode.INTERNAL_ERROR
    assert executor._pending_supervisor is pending and len(created) == 1
    fail[0] = False
    assert executor.run(("C:\\codex.exe",)).error.code is SafeErrorCode.PROVIDER_ERROR and len(created) == 2


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


def test_ready_frame_is_accepted_without_waiting_for_worker_eof():
    from yasb_limitora.codex_helper import _PersistentTransport

    available = iter(((7, False), (0, False)))
    transport = _PersistentTransport(
        1,
        2,
        peek=lambda fd: next(available),
        read=lambda fd, size: b"READY:n",
        nonblocking=True,
    )

    assert transport.read_frame(expected_size=7) == b"READY:n"


def test_persistent_transport_uses_bounded_nonblocking_partial_read_rules():
    from yasb_limitora.codex_helper import _PersistentTransport

    clock = type("Clock", (), {"now": 0.0, "sleep": lambda self, seconds: setattr(self, "now", self.now + seconds)})()
    available = iter(((1, False), (1, False), (0, False), (2, False), (0, False)))
    reads = iter((b"a", BlockingIOError(), b"bc"))

    def read(fd, size):
        value = next(reads)
        if isinstance(value, Exception):
            raise value
        return value

    transport = _PersistentTransport(
        1,
        2,
        peek=lambda fd: next(available),
        read=read,
        clock=lambda: clock.now,
        sleep=clock.sleep,
        nonblocking=True,
    )

    assert transport.read_frame(expected_size=3, timeout_seconds=1) == b"abc"


def test_persistent_response_reader_accepts_header_and_payload_in_one_write():
    from yasb_limitora.codex_helper import _PersistentTransport
    import struct

    stream = bytearray(struct.pack(">I", 3) + b"abc")

    def peek(fd):
        return len(stream), False

    def read(fd, size):
        chunk = bytes(stream[:size])
        del stream[:size]
        return chunk

    transport = _PersistentTransport(1, 2, peek=peek, read=read, nonblocking=True)

    assert transport.read_response() == b"abc"


def test_persistent_response_reader_with_deadline_accepts_header_and_payload_in_one_write():
    from yasb_limitora.codex_helper import _PersistentTransport
    import struct

    stream = bytearray(struct.pack(">I", 3) + b"abc")

    def peek(fd):
        return len(stream), False

    def read(fd, size):
        chunk = bytes(stream[:size])
        del stream[:size]
        return chunk

    transport = _PersistentTransport(1, 2, peek=peek, read=read, nonblocking=True)

    assert transport.read_response_with_deadline(DeadlineContext.from_seconds(1)) == b"abc"
