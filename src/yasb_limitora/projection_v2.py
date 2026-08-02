from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unicodedata import normalize

from .model import (
    PROVIDER_ORDER,
    SAFE_SOURCE_IDS,
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
    SafeErrorCode,
    SnapshotFreshness,
)

_KIND_ORDER = {
    QuotaWindowKind.COMMERCIAL_QUOTA: 0,
    QuotaWindowKind.TECHNICAL_RATE_LIMIT: 1,
    QuotaWindowKind.OTHER: 2,
}
_FAILURES = {
    "invocation_invalid": ("configuration", "invocation_invalid"),
    "configuration_invalid": ("configuration", "invalid_configuration"),
    "internal_error": ("document", "document_aborted"),
}
@dataclass(frozen=True, slots=True)
class V2ProjectionInput:
    """Validated document evidence and the providers enabled for this run."""

    document: DocumentView
    enabled_providers: frozenset[ProviderKey] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.document, DocumentView):
            raise TypeError("document must be a DocumentView")
        try:
            enabled = frozenset(ProviderKey(provider) for provider in self.enabled_providers)
        except (TypeError, ValueError):
            raise ValueError("invalid enabled provider set") from None
        object.__setattr__(self, "enabled_providers", enabled)
def _enum(enum_type: type[Any], value: object, message: str) -> Any:
    if not isinstance(value, enum_type):
        raise ValueError(message)
    return value
def _identity(value: object, message: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > 64
        or any(ord(character) <= 0x1F or ord(character) == 0x7F or 0xD800 <= ord(character) <= 0xDFFF for character in value)
    ):
        raise ValueError(message)
    return value
def _source(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = normalize("NFC", value).strip()
    return candidate if candidate in SAFE_SOURCE_IDS else None
def _timestamp(value: object) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("invalid v2 timestamp")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
def _quantity(quantity: object) -> dict[str, str]:
    if not isinstance(quantity, QuotaQuantity):
        raise ValueError("invalid v2 quantity")
    value = quantity.value
    metric = _enum(QuotaMetricKind, quantity.metric, "invalid v2 quantity metric")
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError("invalid v2 quantity")
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return {"value": rendered or "0", "metric": metric.value, "unit": _identity(quantity.unit, "invalid v2 unit")}
def _window(window: object) -> dict[str, Any]:
    if not isinstance(window, QuotaWindowView):
        raise ValueError("invalid v2 window")
    kind = _enum(QuotaWindowKind, window.kind, "invalid v2 window kind")
    availability = _enum(QuotaAvailability, window.availability, "invalid v2 availability")
    return {
        "kind": kind.value,
        "scope": _identity(window.scope, "invalid v2 scope"),
        "period": _identity(window.period, "invalid v2 period"),
        "plan_id": None if window.plan_id is None else _identity(window.plan_id, "invalid v2 plan id"),
        "availability": availability.value,
        "source_id": _source(window.source_id),
        "limit": None if window.limit is None else _quantity(window.limit),
        "used": None if window.used is None else _quantity(window.used),
        "remaining": None if window.remaining is None else _quantity(window.remaining),
        "reset_at": None if window.reset_at is None else _timestamp(window.reset_at),
    }
def _window_sort_key(window: dict[str, Any]) -> tuple[object, ...]:
    return (
        _KIND_ORDER[QuotaWindowKind(window["kind"])],
        window["scope"],
        window["period"],
        window["plan_id"] is not None,
        window["plan_id"] or "",
        window["source_id"] is not None,
        window["source_id"] or "",
    )
def _error(code: SafeErrorCode) -> dict[str, str]:
    code = _enum(SafeErrorCode, code, "invalid v2 error code")
    mapped = {
        SafeErrorCode.TIMEOUT: "provider_timeout",
        SafeErrorCode.INVALID_PROVIDER_DATA: "invalid_provider_data",
        SafeErrorCode.UNKNOWN_PROVIDER_STATE: "unknown_provider_state",
    }.get(code, "provider_failed")
    return {"code": mapped, "phase": "provider"}
def _fallback(outcome: str) -> dict[str, Any]:
    text = {
        "snapshot": "Quota unavailable",
        "undetected": "Quota not detected",
        "not_run": "Quota not run",
        "execution_error": "Quota error",
    }[outcome]
    return {
        "most_depleted_window": None,
        "compact_text": text,
        "alternate_text": text,
        "tooltip_text": text,
    }
def _provider(view: ProviderView, enabled: frozenset[ProviderKey]) -> tuple[dict[str, Any], str]:
    provider = _enum(ProviderKey, view.provider, "invalid v2 provider")
    state = _enum(ProviderState, view.state, "invalid v2 provider state")
    outcome = view.outcome
    if outcome is None:
        if view.snapshot is not None:
            outcome = ProviderOutcome.SNAPSHOT
        elif state is ProviderState.SAFE_ERROR:
            outcome = ProviderOutcome.EXECUTION_ERROR
        elif state is ProviderState.UNAVAILABLE:
            outcome = ProviderOutcome.UNDETECTED if provider in enabled else ProviderOutcome.NOT_RUN
        else:
            raise ValueError("provider outcome is not representable")
    outcome = _enum(ProviderOutcome, outcome, "invalid v2 provider outcome")

    item: dict[str, Any] = {
        "provider": provider.value,
        "outcome": outcome.value,
        "public_state": None,
        "freshness": None,
        "status_observed_at": None,
        "fetched_at": None,
        "data_at": None,
        "source_id": None,
        "windows": [],
        "execution_error": None,
        "not_run_reason": None,
    }
    if outcome is ProviderOutcome.SNAPSHOT:
        snapshot = view.snapshot
        if not isinstance(snapshot, ProviderSnapshotView) or view.error is not None:
            raise ValueError("invalid v2 snapshot outcome")
        item.update(
            public_state=_enum(PublicProviderState, snapshot.public_state, "invalid v2 public state").value,
            freshness=_enum(SnapshotFreshness, snapshot.freshness, "invalid v2 freshness").value,
            status_observed_at=_timestamp(snapshot.status_observed_at),
            fetched_at=_timestamp(snapshot.fetched_at),
            data_at=_timestamp(snapshot.data_at),
            source_id=_source(snapshot.source_id),
        )
        windows = [_window(window) for window in snapshot.windows]
        item["windows"] = sorted(windows, key=_window_sort_key)
    elif outcome is ProviderOutcome.UNDETECTED:
        if view.snapshot is not None or view.error is not None:
            raise ValueError("invalid v2 undetected outcome")
    elif outcome is ProviderOutcome.NOT_RUN:
        if view.snapshot is not None or view.error is not None or provider in enabled:
            raise ValueError("invalid v2 not-run outcome")
        item["not_run_reason"] = "disabled"
    else:
        if view.snapshot is not None or view.error is None:
            raise ValueError("invalid v2 execution-error outcome")
        item["execution_error"] = _error(view.error.code)
    item.update(_fallback(outcome.value))
    return item, outcome.value
def project_v2_document(input: V2ProjectionInput) -> dict[str, Any]:
    """Build the ordered JSON-compatible v2 document without encoding it."""

    if not isinstance(input, V2ProjectionInput):
        raise TypeError("input must be a V2ProjectionInput")
    views = {view.provider: view for view in input.document.providers}
    if tuple(views) != PROVIDER_ORDER or len(views) != len(PROVIDER_ORDER):
        raise ValueError("document providers are not canonical")
    providers, outcomes = zip(*(_provider(views[provider], input.enabled_providers) for provider in PROVIDER_ORDER))
    successful = {ProviderOutcome.SNAPSHOT.value, ProviderOutcome.UNDETECTED.value}
    if all(outcome in successful for outcome in outcomes):
        execution_state, execution_error = "complete", None
    elif any(outcome in successful for outcome in outcomes):
        execution_state, execution_error = "partial", None
    elif all(outcome == ProviderOutcome.NOT_RUN.value for outcome in outcomes):
        execution_state, execution_error = "not_run", None
    else:
        execution_state, execution_error = "execution_error", {"code": "provider_failed", "phase": "provider"}
    return {
        "version": 2,
        "execution_state": execution_state,
        "execution_error": execution_error,
        "providers": list(providers),
    }
def _encode(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def project_v2_bytes(input: V2ProjectionInput) -> bytes:
    """Return one compact UTF-8 v2 document followed by exactly one LF."""

    return _encode(project_v2_document(input))
def project_v2_failure_bytes(code: str | SafeErrorCode) -> bytes:
    """Return a fixed, redacted v2 document-level failure envelope."""

    value = code.value if isinstance(code, SafeErrorCode) else code
    try:
        phase, reason = _FAILURES[value]
    except (KeyError, TypeError):
        raise ValueError("unsupported v2 document failure") from None
    providers = []
    for provider in PROVIDER_ORDER:
        item = {
            "provider": provider.value,
            "outcome": "not_run",
            "public_state": None,
            "freshness": None,
            "status_observed_at": None,
            "fetched_at": None,
            "data_at": None,
            "source_id": None,
            "windows": [],
            "execution_error": None,
            "not_run_reason": reason,
        }
        item.update(_fallback("not_run"))
        providers.append(item)
    return _encode(
        {
            "version": 2,
            "execution_state": "execution_error",
            "execution_error": {"code": value, "phase": phase},
            "providers": providers,
        }
    )
