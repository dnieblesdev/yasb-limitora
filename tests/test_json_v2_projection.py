import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from yasb_limitora.model import (DocumentView, ProviderKey, ProviderOutcome, ProviderSnapshotView, ProviderState, ProviderView, PublicProviderState, QuotaAvailability, QuotaMetricKind, QuotaQuantity, QuotaWindowKind, QuotaWindowView, SafeError, SafeErrorCode, SnapshotFreshness)
from yasb_limitora.projection_v2 import (
    V2ProjectionInput, project_v2_bytes, project_v2_document, project_v2_failure_bytes,
)

STAMP = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
PKEYS = {"provider", "outcome", "public_state", "freshness", "status_observed_at", "fetched_at", "data_at", "source_id", "windows", "execution_error", "not_run_reason", "most_depleted_window", "compact_text", "alternate_text", "tooltip_text"}
WKEYS = {"kind", "scope", "period", "plan_id", "availability", "source_id", "limit", "used", "remaining", "reset_at"}
QKEYS = {"value", "metric", "unit"}
EKEYS = {"code", "phase"}
TIME = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z$")
ERROR_PHASE = {"invocation_invalid": "configuration", "configuration_invalid": "configuration", "internal_error": "document", "provider_failed": "provider", "provider_timeout": "provider", "invalid_provider_data": "provider", "unknown_provider_state": "provider"}
def _window(period, plan=None, source=None, *, values=True, kind=QuotaWindowKind.COMMERCIAL_QUOTA, scope="account", reset=STAMP):
    metric = QuotaMetricKind.COMMERCIAL_QUOTA if kind is QuotaWindowKind.OTHER else QuotaMetricKind(kind.value)
    quantity = QuotaQuantity(Decimal("100.00"), metric, "percentage_points")
    fields = {"limit": quantity, "used": QuotaQuantity(Decimal("25"), metric, "percentage_points"), "remaining": QuotaQuantity(Decimal("75"), metric, "percentage_points"), "reset_at": reset}
    if not values:
        fields = {"limit": None, "used": None, "remaining": quantity, "reset_at": None}
    return QuotaWindowView(kind, scope, period, plan, QuotaAvailability.KNOWN, source, **fields)
def _snapshot(provider, windows, *, stamp=STAMP):
    snapshot = ProviderSnapshotView(
        PublicProviderState.AVAILABLE, SnapshotFreshness.FRESH, stamp, stamp, stamp,
        "codex-app-server-v2" if provider is ProviderKey.CODEX else "opencode-go-dashboard", tuple(windows),
    )
    return ProviderView(provider, ProviderState.SUCCESS, outcome=ProviderOutcome.SNAPSHOT, snapshot=snapshot)


def _large_document(period_length=64):
    limit, used = Decimal("1" + "0" * 127), Decimal("9" * 127)
    def provider(key, source):
        windows = []
        for index in range(32):
            scope = f"scope{index:02}"
            length = period_length if index == 0 else 64
            period = f"{index:02}" + "p" * (length - 2)
            make_quantity = lambda value: QuotaQuantity(value, QuotaMetricKind.COMMERCIAL_QUOTA, "u" * 64)
            windows.append(QuotaWindowView(QuotaWindowKind.COMMERCIAL_QUOTA, scope, period, None, QuotaAvailability.KNOWN, source, make_quantity(limit), make_quantity(used), make_quantity(Decimal("1")), STAMP))
        return _snapshot(key, windows)
    return _document(provider(ProviderKey.CODEX, "codex-app-server-v2"), provider(ProviderKey.OPENCODE_GO, "opencode-go-dashboard"))
def _document(codex, opencode):
    return DocumentView.ordered(codex, opencode)
def _assert_document(value):
    assert list(value) == ["version", "execution_state", "execution_error", "providers"]
    assert value["version"] == 2 and len(value["providers"]) == 2
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
                if window["limit"] and window["used"]: assert Decimal(window["used"]["value"]) <= Decimal(window["limit"]["value"])
                if window["limit"] and window["remaining"]: assert Decimal(window["remaining"]["value"]) <= Decimal(window["limit"]["value"])
                if all(window[name] for name in ("limit", "used", "remaining")): assert Decimal(window["used"]["value"]) + Decimal(window["remaining"]["value"]) == Decimal(window["limit"]["value"])
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
    projection = V2ProjectionInput(_document(_snapshot(ProviderKey.CODEX, [_window("weekly", "plus"), _window("five_hour")]), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)), {ProviderKey.CODEX, ProviderKey.OPENCODE_GO})
    encoded = project_v2_bytes(projection)
    assert encoded == project_v2_bytes(projection)
    value = json.loads(encoded)
    _assert_document(value)
    assert [window["period"] for window in value["providers"][0]["windows"]] == ["five_hour", "weekly"]


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


def test_presentation_fallbacks_stale_markers_and_depleted_tie_are_observable():
    stale = _snapshot(ProviderKey.CODEX, [_window("five_hour"), _window("weekly", values=False)])
    object.__setattr__(stale.snapshot, "freshness", SnapshotFreshness.STALE)
    value = project_v2_document(V2ProjectionInput(_document(stale, ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)), {ProviderKey.CODEX}))
    provider = value["providers"][0]
    assert provider["most_depleted_window"]["remaining_percentage"] == "75"
    assert provider["compact_text"] == "five_hour: 75% remaining (stale)"
    assert provider["alternate_text"] == "account / five_hour: 75% remaining (stale)"
    assert provider["tooltip_text"].startswith("STALE\n") and "weekly: unavailable" in provider["tooltip_text"]
    tie = project_v2_document(V2ProjectionInput(_document(_snapshot(ProviderKey.CODEX, [_window("z"), _window("a")]), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))))
    assert tie["providers"][0]["most_depleted_window"]["period"] == "a"
    empty = project_v2_document(V2ProjectionInput(_document(_snapshot(ProviderKey.CODEX, []), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))))
    assert empty["providers"][0]["compact_text"] == empty["providers"][0]["alternate_text"] == empty["providers"][0]["tooltip_text"] == "Quota unavailable"
    undetected = project_v2_document(V2ProjectionInput(_document(ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)), {ProviderKey.CODEX, ProviderKey.OPENCODE_GO}))
    assert all(provider["compact_text"] == "Quota not detected" for provider in undetected["providers"])


@pytest.mark.parametrize("availability", (QuotaAvailability.DISABLED, QuotaAvailability.UNAVAILABLE))
def test_public_projection_excludes_numeric_non_known_windows_from_presentation(availability):
    non_eligible = _window("non-eligible")
    object.__setattr__(non_eligible, "availability", availability)
    object.__setattr__(non_eligible, "remaining", QuotaQuantity(Decimal("10"), QuotaMetricKind.COMMERCIAL_QUOTA, "percentage_points"))
    value = project_v2_document(
        V2ProjectionInput(
            _document(_snapshot(ProviderKey.CODEX, [non_eligible, _window("known")]), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))
        )
    )
    provider = value["providers"][0]
    assert provider["most_depleted_window"]["period"] == "known"
    assert "commercial_quota / account / non-eligible: unavailable" in provider["tooltip_text"]
    assert "non-eligible: 10% remaining" not in provider["tooltip_text"]


def test_derived_percentage_uses_decimal34_half_even_at_rounding_boundary():
    remaining = Decimal("12345678901234567890123456789012345")
    limit = Decimal("1" + "0" * 36)
    window = QuotaWindowView(
        QuotaWindowKind.COMMERCIAL_QUOTA,
        "account",
        "boundary",
        None,
        QuotaAvailability.KNOWN,
        "codex-app-server-v2",
        QuotaQuantity(limit, QuotaMetricKind.COMMERCIAL_QUOTA, "percentage_points"),
        QuotaQuantity(limit - remaining, QuotaMetricKind.COMMERCIAL_QUOTA, "percentage_points"),
        QuotaQuantity(remaining, QuotaMetricKind.COMMERCIAL_QUOTA, "percentage_points"),
        STAMP,
    )
    value = project_v2_document(V2ProjectionInput(_document(_snapshot(ProviderKey.CODEX, [window]), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))))
    assert value["providers"][0]["most_depleted_window"]["remaining_percentage"] == "1.234567890123456789012345678901234"


def test_unrepresentable_derived_percentage_fails_closed_without_truncation():
    window = _window("extreme")
    object.__setattr__(window, "limit", QuotaQuantity(Decimal("1e255"), QuotaMetricKind.COMMERCIAL_QUOTA, "percentage_points"))
    object.__setattr__(window, "remaining", QuotaQuantity(Decimal("1"), QuotaMetricKind.COMMERCIAL_QUOTA, "percentage_points"))
    projection = V2ProjectionInput(_document(_snapshot(ProviderKey.CODEX, [window]), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)))
    with pytest.raises(ValueError, match="invalid v2 depleted percentage"):
        project_v2_bytes(projection)


def test_control_character_in_evidence_is_rejected_before_presentation():
    window = _window("safe-period")
    object.__setattr__(window, "period", "safe\nperiod")
    projection = V2ProjectionInput(_document(_snapshot(ProviderKey.CODEX, [window]), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)))
    with pytest.raises(ValueError, match="invalid v2 period") as error:
        project_v2_document(projection)
    assert "safe\\nperiod" not in str(error.value)


def test_presentation_is_bounded_and_sources_are_reviewed_before_emission():
    document = _large_document(64)
    value = project_v2_document(V2ProjectionInput(document))
    for provider in value["providers"]:
        assert len(provider["compact_text"]) <= 128
        assert len(provider["alternate_text"]) <= 128
        assert len(provider["tooltip_text"]) <= 4096
    snapshot = document.providers[0].snapshot
    object.__setattr__(snapshot, "source_id", "private-secret-source")
    object.__setattr__(snapshot.windows[0], "source_id", "workspace-id-secret")
    encoded = project_v2_bytes(V2ProjectionInput(document))
    assert b"private-secret-source" not in encoded and b"workspace-id-secret" not in encoded
    assert json.loads(encoded)["providers"][0]["source_id"] is None


def test_unknown_evidence_fails_closed_without_echoing_the_rejected_value():
    snapshot = _snapshot(ProviderKey.CODEX, [])
    object.__setattr__(snapshot.snapshot, "public_state", "future-secret-state")
    with pytest.raises(ValueError) as error:
        project_v2_document(V2ProjectionInput(_document(snapshot, ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))))
    assert "future-secret-state" not in str(error.value)


@pytest.mark.parametrize(("period_length", "adjustment", "candidate_size"), ((37, "source", 65_535), (37, "scope", 65_536), (64, None, 65_696)))
def test_document_byte_boundaries_are_allowed_or_replaced_whole(period_length, adjustment, candidate_size):
    document = _large_document(period_length)
    if adjustment == "source":
        object.__setattr__(document.providers[0].snapshot, "source_id", "opencode-go-dashboard")
        object.__setattr__(document.providers[0].snapshot.windows[31], "plan_id", "p")
    if adjustment == "scope":
        object.__setattr__(document.providers[0].snapshot.windows[31], "scope", "scope31é")
    encoded = project_v2_bytes(V2ProjectionInput(document))
    if candidate_size <= 65_536:
        assert len(encoded) == candidate_size
    else:
        assert json.loads(encoded)["execution_error"] == {"code": "internal_error", "phase": "document"}


def test_serialized_windows_follow_all_normative_sort_dimensions():
    windows = [_window("a"), _window("b", "plus", "codex-app-server-v2"), _window("a", source="opencode-go-dashboard", scope="b"), _window("a", source="codex-app-server-v2", kind=QuotaWindowKind.TECHNICAL_RATE_LIMIT), _window("z", "plus", "opencode-go-dashboard", scope="z", kind=QuotaWindowKind.OTHER)]
    value = json.loads(project_v2_bytes(V2ProjectionInput(_document(_snapshot(ProviderKey.CODEX, windows), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)))))
    assert [(w["kind"], w["scope"], w["period"], w["plan_id"], w["source_id"]) for w in value["providers"][0]["windows"]] == [("commercial_quota", "account", "a", None, None), ("commercial_quota", "account", "b", "plus", "codex-app-server-v2"), ("commercial_quota", "b", "a", None, "opencode-go-dashboard"), ("technical_rate_limit", "account", "a", None, "codex-app-server-v2"), ("other", "z", "z", "plus", "opencode-go-dashboard")]


def test_null_quantities_and_reset_are_preserved_and_offsets_normalize_to_utc():
    offset = datetime(2026, 8, 1, 8, tzinfo=timezone(timedelta(hours=-4)))
    value = json.loads(project_v2_bytes(V2ProjectionInput(_document(_snapshot(ProviderKey.CODEX, [_window("open", values=False)], stamp=offset), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)))))
    provider, window = value["providers"][0], value["providers"][0]["windows"][0]
    assert provider["status_observed_at"] == "2026-08-01T12:00:00.000000Z"
    assert window["limit"] is None and window["used"] is None and window["reset_at"] is None


def test_invalid_projection_inputs_fail_closed_and_unsupported_document_codes_are_rejected():
    with pytest.raises(TypeError):
        V2ProjectionInput(object())
    with pytest.raises(ValueError):
        V2ProjectionInput(DocumentView.ordered(ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)), {"secret"})
    bad = _snapshot(ProviderKey.CODEX, [])
    object.__setattr__(bad.snapshot, "fetched_at", None)
    with pytest.raises(ValueError):
        project_v2_bytes(V2ProjectionInput(_document(bad, ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))))
    for code in ("provider_failed", "timeout", "unknown", SafeErrorCode.TIMEOUT):
        with pytest.raises(ValueError):
            project_v2_failure_bytes(code)


@pytest.mark.parametrize("code", ("invocation_invalid", "configuration_invalid", "internal_error"))
def test_safe_document_failure_mappings_are_canonical(code):
    value = json.loads(project_v2_failure_bytes(code))
    _assert_document(value)
    assert value["execution_error"] == {"code": code, "phase": "document" if code == "internal_error" else "configuration"}
    reason = {"invocation_invalid": "invocation_invalid", "configuration_invalid": "invalid_configuration", "internal_error": "document_aborted"}[code]
    assert all(provider["not_run_reason"] == reason for provider in value["providers"])
