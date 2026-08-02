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


def test_public_projection_maps_provider_execution_error_safely():
    value = project_v2_document(V2ProjectionInput(_document(ProviderView(ProviderKey.CODEX, ProviderState.SAFE_ERROR, SafeError(SafeErrorCode.TIMEOUT), outcome=ProviderOutcome.EXECUTION_ERROR), ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))))
    assert value["providers"][0]["execution_error"] == {"code": "provider_timeout", "phase": "provider"}
    assert value["providers"][0]["outcome"] == value["execution_state"] == "execution_error"


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
