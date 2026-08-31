import json
import locale
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import cast

import pytest

import yasb_limitora.projection_v2 as projection_module
from yasb_limitora.limitora_api import OpenCodeFailureEvidence
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
from yasb_limitora.projection_v2 import (
    V2ProjectionInput,
    project_v2_bytes,
    project_v2_document,
    project_v2_failure_bytes,
)

STAMP = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
PKEYS = {"provider", "outcome", "public_state", "freshness", "status_observed_at", "fetched_at", "data_at", "source_id", "windows", "execution_error", "not_run_reason", "most_depleted_window", "compact_text", "alternate_text", "tooltip_text"}
WKEYS = {"kind", "scope", "period", "plan_id", "availability", "source_id", "limit", "used", "remaining", "reset_at"}
QKEYS = {"value", "metric", "unit"}
EKEYS = {"code", "phase"}
TIME = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z$")
ERROR_PHASE = {"invocation_invalid": "configuration", "configuration_invalid": "configuration", "internal_error": "document", "provider_failed": "provider", "provider_timeout": "provider", "credential_invalid": "provider", "provider_rate_limited": "provider", "provider_unavailable": "provider", "invalid_provider_data": "provider", "unknown_provider_state": "provider"}
TEST_LOCAL_ZONE = timezone(timedelta(hours=2))


def _format_test_timestamp(value):
    return value.astimezone(TEST_LOCAL_ZONE).strftime("%d/%m/%Y %H:%M:%S")


def _window(period, plan=None, source: str | None = "codex-app-server-v2", *, values=True, kind=QuotaWindowKind.COMMERCIAL_QUOTA, scope="account", reset: datetime | None = STAMP, unit="percentage_points", remaining_value="75"):
    metric = QuotaMetricKind.COMMERCIAL_QUOTA if kind is QuotaWindowKind.OTHER else QuotaMetricKind(kind.value)
    quantity = QuotaQuantity(Decimal("100.00"), metric, unit)
    remaining = Decimal(remaining_value)
    fields = {"limit": quantity, "used": QuotaQuantity(Decimal(100) - remaining, metric, unit), "remaining": QuotaQuantity(remaining, metric, unit), "reset_at": reset}
    if not values:
        fields = {"limit": None, "used": None, "remaining": quantity, "reset_at": None}
    return QuotaWindowView(kind, scope, period, plan, QuotaAvailability.KNOWN, source, **fields)
def _snapshot(provider, windows, *, stamp=STAMP, source=None):
    snapshot = ProviderSnapshotView(
        PublicProviderState.AVAILABLE, SnapshotFreshness.FRESH, stamp, stamp, stamp,
        ("codex-app-server-v2" if provider is ProviderKey.CODEX else "opencode-go-api") if source is None else source, tuple(windows),
    )
    return ProviderView(provider, ProviderState.SUCCESS, outcome=ProviderOutcome.SNAPSHOT, snapshot=snapshot)


def _large_document(period_length=64):
    limit, used = Decimal("1" + "0" * 127), Decimal("9" * 127)
    def provider(key, source):
        windows = []
        kind = QuotaWindowKind.COMMERCIAL_QUOTA if key is ProviderKey.CODEX else QuotaWindowKind.TECHNICAL_RATE_LIMIT
        metric = QuotaMetricKind.COMMERCIAL_QUOTA if key is ProviderKey.CODEX else QuotaMetricKind.TECHNICAL_RATE_LIMIT
        for index in range(32):
            scope = f"scope{index:02}"
            length = period_length if index == 0 else 64
            period = f"{index:02}" + "p" * (length - 2)
            def make_quantity(value):
                return QuotaQuantity(value, metric, "u" * 56)
            windows.append(QuotaWindowView(kind, scope, period, None, QuotaAvailability.KNOWN, source, make_quantity(limit), make_quantity(used), make_quantity(Decimal(1)), STAMP))
        view = _snapshot(key, windows)
        if key is ProviderKey.OPENCODE_GO:
            object.__setattr__(_snapshot_of(view), "public_state", PublicProviderState.RATE_LIMITED)
        return view
    return _document(provider(ProviderKey.CODEX, "codex-app-server-v2"), provider(ProviderKey.OPENCODE_GO, "opencode-go-api"))
def _document(codex, opencode):
    return DocumentView.ordered(codex, opencode)


def _snapshot_of(view: ProviderView) -> ProviderSnapshotView:
    assert view.snapshot is not None
    return view.snapshot


def _near_boundary_document(accent_count):
    document = _large_document(64)
    index = 0
    for provider in document.providers:
        for window in _snapshot_of(provider).windows:
            object.__setattr__(window, "plan_id", "p" * 64)
            suffix = "é" if 1 <= index <= accent_count else "s"
            object.__setattr__(window, "scope", "s" * 63 + suffix)
            index += 1
    return document
def _assert_document(value):
    assert list(value) == ["execution_state", "execution_error", "providers"]
    assert "version" not in value and len(value["providers"]) == 2
    assert [p["provider"] for p in value["providers"]] == ["codex", "opencode_go"]
    outcomes = []
    for provider in value["providers"]:
        assert set(provider) == PKEYS
        outcome = provider["outcome"]
        outcomes.append(outcome)
        assert outcome in {"snapshot", "undetected", "not_run", "execution_error"}
        assert all(isinstance(provider[name], str) and len(provider[name]) <= limit and not any(ord(c) < 32 or ord(c) == 127 for c in provider[name]) for name, limit in (("compact_text", 128), ("alternate_text", 128)))
        assert isinstance(provider["tooltip_text"], str) and len(provider["tooltip_text"]) <= 4096 and not any((ord(c) < 32 and c != "\n") or ord(c) == 127 for c in provider["tooltip_text"])
        if outcome == "snapshot":
            assert isinstance(provider["public_state"], str) and provider["freshness"] in {"fresh", "stale"}
            assert all(TIME.fullmatch(provider[name]) for name in ("status_observed_at", "fetched_at", "data_at"))
            assert provider["execution_error"] is None and provider["not_run_reason"] is None
        else:
            assert all(provider[name] is None for name in ("public_state", "freshness", "status_observed_at", "fetched_at", "data_at", "source_id"))
            assert provider["windows"] == []
            if outcome == "undetected":
                assert provider["execution_error"] is None and provider["not_run_reason"] is None
            elif outcome == "not_run":
                assert provider["execution_error"] is None and isinstance(provider["not_run_reason"], str)
            else:
                assert set(provider["execution_error"]) == EKEYS and provider["not_run_reason"] is None
                assert ERROR_PHASE[provider["execution_error"]["code"]] == provider["execution_error"]["phase"]
        for window in provider["windows"]:
            assert set(window) == WKEYS
            assert window["kind"] in {"commercial_quota", "technical_rate_limit", "other"}
            assert all(isinstance(window[name], str) and window[name] for name in ("scope", "period"))
            if window["availability"] == "known":
                assert any(window[name] is not None for name in ("limit", "used", "remaining"))
                for name in ("limit", "used", "remaining"):
                    if window[name] is not None:
                        assert set(window[name]) == QKEYS and type(window[name]["value"]) is str and re.fullmatch(r"0|[1-9]\d*(\.\d+)?", window[name]["value"])
                        assert window[name]["metric"] == (window["kind"] if window["kind"] != "other" else window[name]["metric"])
                        assert isinstance(window[name]["unit"], str) and window[name]["unit"]
                if window["limit"] and window["used"]:
                    assert Decimal(window["used"]["value"]) <= Decimal(window["limit"]["value"])
                if window["limit"] and window["remaining"]:
                    assert Decimal(window["remaining"]["value"]) <= Decimal(window["limit"]["value"])
                if all(window[name] for name in ("limit", "used", "remaining")):
                    assert Decimal(window["used"]["value"]) + Decimal(window["remaining"]["value"]) == Decimal(window["limit"]["value"])
            else:
                assert all(window[name] is None for name in ("limit", "used", "remaining", "reset_at"))
            assert window["availability"] in {"known", "unlimited", "disabled", "unavailable", "unknown", "not_authorized", "not_applicable", "invalid", "error"}
            assert window["reset_at"] is None or TIME.fullmatch(window["reset_at"])
    successful = {"snapshot", "undetected"}
    if all(outcome in successful for outcome in outcomes):
        assert value["execution_state"] == "complete" and value["execution_error"] is None
    elif any(outcome in successful for outcome in outcomes):
        assert value["execution_state"] == "partial" and value["execution_error"] is None
    elif all(outcome == "not_run" for outcome in outcomes):
        assert value["execution_state"] == "not_run" or value["execution_state"] == "execution_error"
    else:
        assert value["execution_state"] == "execution_error" and set(value["execution_error"]) == EKEYS


def test_snapshot_projection_has_schema_and_semantic_invariants():
    projection = V2ProjectionInput(_document(_snapshot(ProviderKey.CODEX, [_window("weekly", "plus"), _window("five_hour")]), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)), frozenset({ProviderKey.CODEX, ProviderKey.OPENCODE_GO}))
    encoded = project_v2_bytes(projection)
    assert encoded == project_v2_bytes(projection)
    value = json.loads(encoded)
    _assert_document(value)
    assert [window["period"] for window in value["providers"][0]["windows"]] == ["five_hour", "weekly"]


def test_fresh_snapshot_uses_the_published_grammar_and_nullable_identities():
    window = _window("weekly")
    object.__setattr__(window, "reset_at", None)
    provider = project_v2_document(
        V2ProjectionInput(_document(_snapshot(ProviderKey.CODEX, [window]), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)))
    )["providers"][0]
    assert set(provider["most_depleted_window"]) == {"kind", "scope", "period", "plan_id", "unit", "source_id", "remaining_percentage"}
    assert provider["most_depleted_window"]["plan_id"] is None
    assert provider["most_depleted_window"]["source_id"] == "codex-app-server-v2"
    assert provider["compact_text"] == "Quota 75% remaining; state=available; freshness=fresh"
    assert provider["alternate_text"] == "Quota account / weekly: 75% remaining; state=available; freshness=fresh"
    assert provider["tooltip_text"] == (
        "Codex\nState: Available · Fresh\nLowest quota: 75% remaining\n"
        "Weekly: 75% remaining"
    )


def test_tooltip_formats_utc_resets_injected_local_timezone_and_locale_format():
    windows = [
        _window("weekly", source="opencode-go-api", remaining_value="60", reset=datetime(2026, 8, 24, tzinfo=timezone.utc)),
        _window("monthly", source="opencode-go-api", remaining_value="5", reset=datetime(2026, 9, 6, 18, 35, 42, 123456, tzinfo=timezone.utc)),
        _window("five_hour", source="opencode-go-api", remaining_value="100", reset=datetime(2026, 8, 18, 11, 42, 59, 999999, tzinfo=timezone.utc)),
    ]
    provider = project_v2_document(
        V2ProjectionInput(_document(ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE), _snapshot(ProviderKey.OPENCODE_GO, windows))),
        timestamp_formatter=_format_test_timestamp,
    )["providers"][1]

    assert provider["tooltip_text"] == (
        "OpenCode Go\nState: Available · Fresh\nLowest quota: 5% remaining\n"
        "5-hour: 100% remaining · resets 18/08/2026 13:42:59\n"
        "Monthly: 5% remaining · resets 06/09/2026 20:35:42\n"
        "Weekly: 60% remaining · resets 24/08/2026 02:00:00"
    )


def test_tooltip_never_invents_zero_for_unavailable_partial_windows():
    partial = _snapshot(ProviderKey.OPENCODE_GO, [])
    object.__setattr__(_snapshot_of(partial), "public_state", PublicProviderState.PARTIAL)
    tooltip = project_v2_document(
        V2ProjectionInput(_document(ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE), partial))
    )["providers"][1]["tooltip_text"]

    assert tooltip == (
        "OpenCode Go\nState: Partial · Fresh\nLowest quota: Quota unavailable\n"
        "5-hour: Quota unavailable\nMonthly: Quota unavailable\nWeekly: Quota unavailable"
    )
    assert "0%" not in tooltip


@pytest.mark.parametrize(
    ("provider_key", "source", "expected"),
    (
        (
            ProviderKey.CODEX,
            "codex-app-server-v2",
            "Codex\nState: Available · Fresh\nLowest quota: Quota unavailable\nWeekly: Quota unavailable\nResets: 20/08/2026 05:35:00",
        ),
        (
            ProviderKey.OPENCODE_GO,
            "opencode-go-api",
            "OpenCode Go\nState: Available · Fresh\nLowest quota: Quota unavailable\n5-hour: Quota unavailable\nMonthly: Quota unavailable\nWeekly: Quota unavailable · resets 20/08/2026 05:35:00",
        ),
    ),
)
def test_tooltip_keeps_a_valid_reset_when_percentage_basis_is_unavailable(provider_key, source, expected):
    window = _window("weekly", source=source, values=False)
    object.__setattr__(window, "reset_at", datetime(2026, 8, 20, 3, 35, tzinfo=timezone.utc))
    document = _document(
        _snapshot(ProviderKey.CODEX, [window]) if provider_key is ProviderKey.CODEX else ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE),
        _snapshot(ProviderKey.OPENCODE_GO, [window]) if provider_key is ProviderKey.OPENCODE_GO else ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE),
    )

    provider = project_v2_document(
        V2ProjectionInput(document),
        timestamp_formatter=_format_test_timestamp,
    )["providers"][0 if provider_key is ProviderKey.CODEX else 1]

    assert provider["most_depleted_window"] is None
    assert provider["tooltip_text"] == expected


def test_tooltip_reset_converts_non_utc_offset_before_injected_local_formatting():
    window = _window(
        "weekly",
        source="opencode-go-api",
        reset=datetime(2026, 8, 24, tzinfo=timezone(timedelta(hours=-4))),
        remaining_value="60",
    )
    provider = project_v2_document(
        V2ProjectionInput(_document(ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE), _snapshot(ProviderKey.OPENCODE_GO, [window]))),
        timestamp_formatter=_format_test_timestamp,
    )["providers"][1]

    assert "Weekly: 60% remaining · resets 24/08/2026 06:00:00" in provider["tooltip_text"]


def test_local_timestamp_formatter_uses_stable_fallback_when_locale_format_is_unavailable(monkeypatch):
    def unavailable_locale_format(_value):
        raise ValueError("locale formatting unavailable")

    monkeypatch.setattr(projection_module, "_locale_datetime_format", unavailable_locale_format)

    assert projection_module._format_local_datetime(
        datetime(2026, 8, 24, 0, 0, 59, 999999, tzinfo=timezone.utc),
        local_zone=TEST_LOCAL_ZONE,
    ) == "2026-08-24 02:00:59"


def test_local_timestamp_fallback_does_not_mutate_process_locale(monkeypatch):
    before_time = locale.setlocale(locale.LC_TIME)
    before_all = locale.setlocale(locale.LC_ALL)

    def unavailable_locale_format(_value):
        raise ValueError("locale formatting unavailable")

    monkeypatch.setattr(projection_module, "_locale_datetime_format", unavailable_locale_format)

    assert projection_module._format_local_datetime(
        datetime(2026, 8, 24, 0, 0, 59, tzinfo=timezone.utc),
        local_zone=TEST_LOCAL_ZONE,
    ) == "2026-08-24 02:00:59"
    assert locale.setlocale(locale.LC_TIME) == before_time
    assert locale.setlocale(locale.LC_ALL) == before_all


def test_tooltip_marks_partial_stale_codex_data_and_missing_reset_without_zero():
    snapshot = _snapshot(ProviderKey.CODEX, [_window("weekly", reset=None, remaining_value="0")])
    object.__setattr__(_snapshot_of(snapshot), "public_state", PublicProviderState.PARTIAL)
    object.__setattr__(_snapshot_of(snapshot), "freshness", SnapshotFreshness.STALE)
    tooltip = project_v2_document(
        V2ProjectionInput(_document(snapshot, ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)))
    )["providers"][0]["tooltip_text"]

    assert tooltip == "Codex\nState: Partial · Stale\nLowest quota: 0% remaining\nWeekly: 0% remaining"
    assert "resets" not in tooltip.lower()


def test_tooltip_lowest_quota_uses_the_most_depleted_window_not_the_first_window():
    snapshot = _snapshot(
        ProviderKey.CODEX,
        [
            _window("five_hour", remaining_value="100", reset=None),
            _window("weekly", remaining_value="0", reset=None),
        ],
    )
    provider = project_v2_document(
        V2ProjectionInput(_document(snapshot, ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)))
    )["providers"][0]
    tooltip = provider["tooltip_text"]

    assert provider["most_depleted_window"]["period"] == "weekly"
    assert tooltip.splitlines()[:4] == [
        "Codex",
        "State: Available · Fresh",
        "Lowest quota: 0% remaining",
        "5-hour: 100% remaining",
    ]
    assert tooltip.splitlines()[4] == "Weekly: 0% remaining"


def test_public_projection_maps_all_disabled_providers_to_not_run():
    value = project_v2_document(V2ProjectionInput(_document(ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))))
    assert value["execution_state"] == "not_run"
    assert [(p["outcome"], p["not_run_reason"]) for p in value["providers"]] == [("not_run", "disabled"), ("not_run", "disabled")]
    assert all(provider["compact_text"] == "Quota not run" for provider in value["providers"])
    assert all(provider["alternate_text"] == "Quota not run" for provider in value["providers"])
    assert all(provider["tooltip_text"] == "Quota not run: provider disabled" for provider in value["providers"])


def test_public_projection_maps_provider_execution_error_safely():
    value = project_v2_document(V2ProjectionInput(_document(ProviderView(ProviderKey.CODEX, ProviderState.SAFE_ERROR, SafeError(SafeErrorCode.TIMEOUT), outcome=ProviderOutcome.EXECUTION_ERROR), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))))
    provider = value["providers"][0]
    assert provider["execution_error"] == {"code": "provider_timeout", "phase": "provider"}
    assert provider["outcome"] == value["execution_state"] == "execution_error"
    assert provider["compact_text"] == provider["alternate_text"] == provider["tooltip_text"] == "Quota error"


@pytest.mark.parametrize(
    ("evidence", "mapped"),
    (
        (OpenCodeFailureEvidence.CREDENTIAL_INVALID, "credential_invalid"),
        (OpenCodeFailureEvidence.TIMEOUT, "provider_timeout"),
        (OpenCodeFailureEvidence.RATE_LIMITED, "provider_rate_limited"),
        (OpenCodeFailureEvidence.UNAVAILABLE, "provider_unavailable"),
    ),
)
def test_opencode_private_sidecar_maps_only_the_bounded_v2_taxonomy(evidence, mapped):
    document = _document(
        ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE),
        ProviderView(
            ProviderKey.OPENCODE_GO,
            ProviderState.SAFE_ERROR,
            SafeError(SafeErrorCode.PROVIDER_ERROR),
            outcome=ProviderOutcome.EXECUTION_ERROR,
        ),
    )

    projection = V2ProjectionInput(document, opencode_evidence=evidence)
    value = project_v2_document(projection)

    assert "version" not in value
    assert "OpenCodeFailureEvidence" not in repr(projection)
    assert [provider["provider"] for provider in value["providers"]] == ["codex", "opencode_go"]
    assert value["providers"][1]["execution_error"] == {"code": mapped, "phase": "provider"}
    assert value["execution_error"] == {"code": "provider_failed", "phase": "provider"}


def test_presentation_fallbacks_stale_markers_and_depleted_tie_are_observable():
    stale = _snapshot(ProviderKey.CODEX, [_window("five_hour"), _window("weekly", values=False)])
    object.__setattr__(_snapshot_of(stale), "freshness", SnapshotFreshness.STALE)
    value = project_v2_document(
        V2ProjectionInput(_document(stale, ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)), frozenset({ProviderKey.CODEX})),
        timestamp_formatter=_format_test_timestamp,
    )
    provider = value["providers"][0]
    assert provider["most_depleted_window"]["remaining_percentage"] == "75"
    assert provider["compact_text"] == "Quota 75% remaining; state=available; freshness=stale"
    assert provider["alternate_text"] == "Quota account / five_hour: 75% remaining; state=available; freshness=stale"
    assert provider["tooltip_text"] == (
        "Codex\nState: Available · Stale\nLowest quota: 75% remaining\n"
        "5-hour: 75% remaining\nWeekly: Quota unavailable\nResets: 01/08/2026 14:00:00"
    )
    tie = project_v2_document(V2ProjectionInput(_document(_snapshot(ProviderKey.CODEX, [_window("z"), _window("a")]), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))))
    assert tie["providers"][0]["most_depleted_window"]["period"] == "a"
    empty = project_v2_document(V2ProjectionInput(_document(_snapshot(ProviderKey.CODEX, []), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))))
    assert empty["providers"][0]["compact_text"] == "Quota percentage unavailable; state=available; freshness=fresh"
    assert empty["providers"][0]["alternate_text"] == empty["providers"][0]["compact_text"]
    assert empty["providers"][0]["tooltip_text"] == "Codex\nState: Available · Fresh\nLowest quota: Quota unavailable\nNo quota windows"
    undetected = project_v2_document(V2ProjectionInput(_document(ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)), frozenset({ProviderKey.CODEX, ProviderKey.OPENCODE_GO})))
    assert all(provider["compact_text"] == "Quota not detected" for provider in undetected["providers"])


@pytest.mark.parametrize("availability", (QuotaAvailability.DISABLED, QuotaAvailability.UNAVAILABLE))
def test_public_projection_excludes_numeric_non_known_windows_from_presentation(availability):
    non_eligible = _window("non-eligible")
    object.__setattr__(non_eligible, "availability", availability)
    object.__setattr__(non_eligible, "remaining", QuotaQuantity(Decimal(10), QuotaMetricKind.COMMERCIAL_QUOTA, "percentage_points"))
    value = project_v2_document(
        V2ProjectionInput(
            _document(_snapshot(ProviderKey.CODEX, [non_eligible, _window("known")]), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))
        )
    )
    provider = value["providers"][0]
    assert provider["most_depleted_window"]["period"] == "known"
    assert "Non-eligible: Quota unavailable" in provider["tooltip_text"]
    assert "non-eligible: 10% remaining" not in provider["tooltip_text"]


def test_derived_percentage_uses_decimal34_half_even_at_rounding_boundary():
    remaining = Decimal(12345678901234567890123456789012345)
    limit = Decimal("1" + "0" * 36)
    window = QuotaWindowView(
        QuotaWindowKind.COMMERCIAL_QUOTA,
        "account",
        "boundary",
        "codex-app-server-v2",
        QuotaAvailability.KNOWN,
        "codex-app-server-v2",
        QuotaQuantity(limit, QuotaMetricKind.COMMERCIAL_QUOTA, "percentage_points"),
        QuotaQuantity(limit - remaining, QuotaMetricKind.COMMERCIAL_QUOTA, "percentage_points"),
        QuotaQuantity(remaining, QuotaMetricKind.COMMERCIAL_QUOTA, "percentage_points"),
        STAMP,
    )
    value = project_v2_document(V2ProjectionInput(_document(_snapshot(ProviderKey.CODEX, [window]), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))))
    assert value["providers"][0]["most_depleted_window"]["remaining_percentage"] == "1.234567890123456789012345678901234"


def test_unrepresentable_derived_percentage_fails_closed_without_synthetic_basis():
    window = _window("extreme")
    object.__setattr__(window, "limit", QuotaQuantity(Decimal("1e255"), QuotaMetricKind.COMMERCIAL_QUOTA, "percentage_points"))
    object.__setattr__(window, "remaining", QuotaQuantity(Decimal(1), QuotaMetricKind.COMMERCIAL_QUOTA, "percentage_points"))
    projection = V2ProjectionInput(_document(_snapshot(ProviderKey.CODEX, [window]), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)))
    provider = project_v2_document(projection)["providers"][0]
    assert provider["most_depleted_window"] is None
    assert "Extreme: Quota unavailable" in provider["tooltip_text"]


def test_tooltip_unit_comes_only_from_consistent_quantity_evidence():
    def tooltip(window):
        value = project_v2_document(
            V2ProjectionInput(_document(_snapshot(ProviderKey.CODEX, [window]), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)))
        )
        return value["providers"][0]["tooltip_text"]

    remaining_only = _window("remaining-only", values=False, unit="widgets")
    used_only = QuotaWindowView(
        QuotaWindowKind.COMMERCIAL_QUOTA,
        "account",
        "used-only",
        None,
        QuotaAvailability.KNOWN,
        "codex-app-server-v2",
        used=QuotaQuantity(Decimal(7), QuotaMetricKind.COMMERCIAL_QUOTA, "widgets"),
    )
    missing_limit = QuotaWindowView(
        QuotaWindowKind.COMMERCIAL_QUOTA,
        "account",
        "missing-limit",
        None,
        QuotaAvailability.KNOWN,
        "codex-app-server-v2",
        used=QuotaQuantity(Decimal(3), QuotaMetricKind.COMMERCIAL_QUOTA, "widgets"),
        remaining=QuotaQuantity(Decimal(7), QuotaMetricKind.COMMERCIAL_QUOTA, "widgets"),
    )
    mismatched = _window("mismatched", unit="widgets")
    object.__setattr__(mismatched, "used", QuotaQuantity(Decimal(25), QuotaMetricKind.COMMERCIAL_QUOTA, "requests"))

    for window in (remaining_only, used_only, missing_limit, mismatched):
        value = tooltip(window)
        assert "unit=" not in value
        assert "scope=" not in value
        assert "source_id" not in value
        if window is not mismatched:
            assert "Quota unavailable" in value


@pytest.mark.parametrize(
    ("code", "mapped", "phase"),
    (
        (SafeErrorCode.TIMEOUT, "provider_timeout", "provider"),
        (SafeErrorCode.INVALID_PROVIDER_DATA, "invalid_provider_data", "provider"),
        (SafeErrorCode.UNKNOWN_PROVIDER_STATE, "unknown_provider_state", "provider"),
        (SafeErrorCode.PROVIDER_ERROR, "provider_failed", "provider"),
    ),
)
def test_presentation_contract_maps_not_run_and_safe_errors_without_raw_details(code, mapped, phase):
    error = project_v2_document(
        V2ProjectionInput(
            _document(
                ProviderView(ProviderKey.CODEX, ProviderState.SAFE_ERROR, SafeError(code), outcome=ProviderOutcome.EXECUTION_ERROR),
                ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE),
            )
        )
    )["providers"][0]
    assert error["execution_error"] == {"code": mapped, "phase": phase}
    assert error["compact_text"] == error["alternate_text"] == error["tooltip_text"] == "Quota error"

    not_run = json.loads(project_v2_failure_bytes("internal_error"))["providers"][0]
    assert not_run["outcome"] == "not_run"
    assert not_run["not_run_reason"] == "document_aborted"
    assert not_run["compact_text"] == not_run["alternate_text"] == "Quota not run"
    assert not_run["tooltip_text"] == "Quota not run: document aborted"


def test_tooltip_quotes_identity_delimiters_and_backslashes():
    window = _window("five=hour", scope="team;west", unit=r"requests\hour")
    projection = V2ProjectionInput(_document(_snapshot(ProviderKey.CODEX, [window]), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)))
    provider = project_v2_document(projection)["providers"][0]

    assert "Five=hour: 75% remaining" in provider["tooltip_text"]
    assert 'Quota "team;west" / "five=hour": 75% remaining' in provider["alternate_text"]
    assert "scope=" not in provider["tooltip_text"]
    assert "period=" not in provider["tooltip_text"]
    assert "unit=" not in provider["tooltip_text"]
    assert "source_id" not in provider["tooltip_text"]


def test_presentation_is_bounded_and_sources_are_reviewed_before_emission():
    document = _large_document(64)
    value = project_v2_document(V2ProjectionInput(document))
    for provider in value["providers"]:
        assert len(provider["compact_text"]) <= 128
        assert len(provider["alternate_text"]) <= 128
        assert len(provider["tooltip_text"]) <= 4096
    snapshot = _snapshot_of(document.providers[0])
    object.__setattr__(snapshot, "source_id", "private-secret-source")
    object.__setattr__(snapshot.windows[0], "source_id", "workspace-id-secret")
    encoded = project_v2_bytes(V2ProjectionInput(document))
    assert b"private-secret-source" not in encoded and b"workspace-id-secret" not in encoded
    assert json.loads(encoded)["providers"][0]["source_id"] is None


def test_projection_normalizes_root_and_window_sources_per_provider_and_drops_untrusted_quantities():
    document = _document(
        _snapshot(ProviderKey.CODEX, [_window("weekly", source=None)], source="opencode-go-api"),
        _snapshot(ProviderKey.OPENCODE_GO, [_window("weekly", source="codex-app-server-v2")], source="codex-app-server-v2"),
    )
    for view in document.providers:
        window = _snapshot_of(view).windows[0]
        object.__setattr__(window, "availability", "malformed")
        object.__setattr__(window, "limit", object())
        object.__setattr__(window, "reset_at", object())

    value = project_v2_document(V2ProjectionInput(document))

    for provider in value["providers"]:
        assert provider["source_id"] is None
        window = provider["windows"][0]
        assert window["source_id"] is None
        assert window["availability"] == "unavailable"
        assert all(window[field] is None for field in ("limit", "used", "remaining", "reset_at"))


def test_opencode_projection_completes_fixed_slots_when_root_source_is_null():
    known = _window("five_hour", source="opencode-go-api")
    duplicate = _window("weekly", source="opencode-go-api", scope="team")
    other_duplicate = _window("weekly", source="opencode-go-api", scope="workspace")
    snapshot = _snapshot(ProviderKey.OPENCODE_GO, [known, duplicate, other_duplicate])
    object.__setattr__(_snapshot_of(snapshot), "source_id", None)
    value = project_v2_document(V2ProjectionInput(_document(ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE), snapshot)))

    provider = value["providers"][1]
    assert provider["source_id"] is None
    commercial = [window for window in provider["windows"] if window["kind"] == "commercial_quota"]
    assert [window["period"] for window in commercial] == ["five_hour", "monthly", "weekly"]
    assert commercial[0]["source_id"] == "opencode-go-api"
    assert commercial[2]["scope"] == "account"
    for window in commercial[1:]:
        assert window["availability"] == "unavailable"
        assert window["source_id"] is None
        assert all(window[field] is None for field in ("plan_id", "limit", "used", "remaining", "reset_at"))
    swapped = _snapshot(ProviderKey.OPENCODE_GO, [known, other_duplicate, duplicate])
    object.__setattr__(_snapshot_of(swapped), "source_id", None)
    assert project_v2_bytes(V2ProjectionInput(_document(ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE), snapshot))) == project_v2_bytes(V2ProjectionInput(_document(ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE), swapped)))


def test_opencode_projection_rate_limited_preserves_only_technical_windows_and_allows_empty():
    technical = _window("requests", source="opencode-go-api", kind=QuotaWindowKind.TECHNICAL_RATE_LIMIT)
    rate_limited = _snapshot(ProviderKey.OPENCODE_GO, [technical])
    object.__setattr__(_snapshot_of(rate_limited), "public_state", PublicProviderState.RATE_LIMITED)
    empty = _snapshot(ProviderKey.OPENCODE_GO, [])
    object.__setattr__(_snapshot_of(empty), "public_state", PublicProviderState.RATE_LIMITED)

    for snapshot, expected in ((rate_limited, [("technical_rate_limit", "opencode-go-api")]), (empty, [])):
        value = project_v2_document(V2ProjectionInput(_document(ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE), snapshot)))
        assert [(window["kind"], window["source_id"]) for window in value["providers"][1]["windows"]] == expected


def test_summary_truncation_preserves_the_complete_qualifier_and_tooltip_lines():
    document = _document(_snapshot(ProviderKey.CODEX, [_window("p" * 64, "x" * 64)]), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))
    provider = project_v2_document(V2ProjectionInput(document))["providers"][0]
    assert len(provider["compact_text"]) <= 128 and len(provider["alternate_text"]) <= 128
    assert provider["compact_text"].endswith("; state=available; freshness=fresh")
    assert provider["alternate_text"].endswith("; state=available; freshness=fresh")
    lines = provider["tooltip_text"].splitlines()
    assert lines[:3] == ["Codex", "State: Available · Fresh", "Lowest quota: 75% remaining"]
    assert all(not any(field in line for field in ("kind=", "scope=", "plan_id=", "unit=", "source_id=")) for line in lines)


def test_unknown_evidence_fails_closed_without_echoing_the_rejected_value():
    snapshot = _snapshot(ProviderKey.CODEX, [])
    object.__setattr__(_snapshot_of(snapshot), "public_state", "future-secret-state")
    with pytest.raises(ValueError) as error:
        project_v2_document(V2ProjectionInput(_document(snapshot, ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))))
    assert "future-secret-state" not in str(error.value)


@pytest.mark.parametrize(("adjustment", "candidate_size"), (("boundary_65389", 65_389), ("boundary_65390", 65_390), ("oversize", 65_696)))
def test_document_byte_boundaries_are_allowed_or_replaced_whole(adjustment, candidate_size):
    if adjustment == "boundary_65389":
        document = _near_boundary_document(39)
    elif adjustment == "boundary_65390":
        document = _near_boundary_document(40)
    else:
        document = _large_document(64)
    if adjustment == "oversize":
        for provider in document.providers:
            for window in _snapshot_of(provider).windows:
                object.__setattr__(window, "plan_id", "p" * 64)
                object.__setattr__(window, "scope", "é" * 64)
    raw = json.dumps(
        project_v2_document(V2ProjectionInput(document), timestamp_formatter=_format_test_timestamp),
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8") + b"\n"
    encoded = project_v2_bytes(V2ProjectionInput(document), timestamp_formatter=_format_test_timestamp)
    assert len(encoded) <= 65_536
    if candidate_size <= 65_536:
        assert len(encoded) == candidate_size
        value = json.loads(encoded)
        assert value["execution_error"] is None
        assert all(
            provider["outcome"] == "snapshot"
            and len(provider["windows"]) == 32
            and provider["most_depleted_window"] is not None
            for provider in value["providers"]
        )
        assert len(raw) > 65_536
    else:
        value = json.loads(encoded)
        _assert_document(value)
        assert value["execution_state"] == "execution_error"
        assert value["execution_error"] == {"code": "internal_error", "phase": "document"}
        assert all(
            provider["outcome"] == "not_run"
            and provider["execution_error"] is None
            and provider["not_run_reason"] == "document_aborted"
            and provider["most_depleted_window"] is None
            and provider["compact_text"] == "Quota not run"
            and provider["alternate_text"] == "Quota not run"
            and provider["tooltip_text"] == "Quota not run: document aborted"
            for provider in value["providers"]
        )
        assert b'"outcome":"snapshot"' not in encoded


def test_serialized_windows_follow_all_normative_sort_dimensions():
    windows = [_window("a"), _window("b", "plus", "codex-app-server-v2"), _window("a", source="codex-app-server-v2", scope="b"), _window("a", source="codex-app-server-v2", kind=QuotaWindowKind.TECHNICAL_RATE_LIMIT), _window("z", "plus", "codex-app-server-v2", scope="z", kind=QuotaWindowKind.OTHER)]
    value = json.loads(project_v2_bytes(V2ProjectionInput(_document(_snapshot(ProviderKey.CODEX, windows), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)))))
    assert [(w["kind"], w["scope"], w["period"], w["plan_id"], w["source_id"]) for w in value["providers"][0]["windows"]] == [("commercial_quota", "account", "a", None, "codex-app-server-v2"), ("commercial_quota", "account", "b", "plus", "codex-app-server-v2"), ("commercial_quota", "b", "a", None, "codex-app-server-v2"), ("technical_rate_limit", "account", "a", None, "codex-app-server-v2"), ("other", "z", "z", "plus", "codex-app-server-v2")]


def test_presentation_is_identical_for_equivalent_window_permutations():
    first = _snapshot(ProviderKey.CODEX, [_window("weekly"), _window("five_hour")])
    second = _snapshot(ProviderKey.CODEX, [_window("five_hour"), _window("weekly")])
    left = project_v2_bytes(V2ProjectionInput(_document(first, ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))))
    right = project_v2_bytes(V2ProjectionInput(_document(second, ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))))
    assert left == right
    assert json.loads(left)["providers"][0]["most_depleted_window"]["period"] == "five_hour"


def test_null_quantities_and_reset_are_preserved_and_offsets_normalize_to_utc():
    offset = datetime(2026, 8, 1, 8, tzinfo=timezone(timedelta(hours=-4)))
    value = json.loads(project_v2_bytes(V2ProjectionInput(_document(_snapshot(ProviderKey.CODEX, [_window("open", values=False)], stamp=offset), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)))))
    provider, window = value["providers"][0], value["providers"][0]["windows"][0]
    assert provider["status_observed_at"] == "2026-08-01T12:00:00.000000Z"
    assert window["limit"] is None and window["used"] is None and window["reset_at"] is None


def test_invalid_projection_inputs_fail_closed_and_unsupported_document_codes_are_rejected():
    with pytest.raises(TypeError):
        V2ProjectionInput(cast(DocumentView, object()))
    with pytest.raises(ValueError):
        V2ProjectionInput(DocumentView.ordered(ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)), cast(frozenset[ProviderKey], {"secret"}))
    with pytest.raises(ValueError):
        V2ProjectionInput(DocumentView.ordered(ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)), opencode_evidence=object())
    bad = _snapshot(ProviderKey.CODEX, [])
    object.__setattr__(_snapshot_of(bad), "fetched_at", None)
    with pytest.raises(ValueError):
        project_v2_bytes(V2ProjectionInput(_document(bad, ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))))
    for code in ("provider_failed", "timeout", "unknown", SafeErrorCode.TIMEOUT):
        with pytest.raises(ValueError):
            project_v2_failure_bytes(code)
    overflow = _large_document()
    object.__setattr__(_snapshot_of(overflow.providers[1]), "public_state", PublicProviderState.AVAILABLE)
    value = json.loads(project_v2_bytes(V2ProjectionInput(overflow)))
    assert value["execution_error"] == {"code": "internal_error", "phase": "document"}
    _assert_document(value)


@pytest.mark.parametrize("code", ("invocation_invalid", "configuration_invalid", "internal_error"))
def test_safe_document_failure_mappings_are_canonical(code):
    value = json.loads(project_v2_failure_bytes(code))
    _assert_document(value)
    assert value["execution_error"] == {"code": code, "phase": "document" if code == "internal_error" else "configuration"}
    reason = {"invocation_invalid": "invocation_invalid", "configuration_invalid": "invalid_configuration", "internal_error": "document_aborted"}[code]
    assert all(provider["not_run_reason"] == reason for provider in value["providers"])
