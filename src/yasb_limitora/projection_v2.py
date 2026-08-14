from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from typing import Any
from unicodedata import normalize

from .limitora_api import OpenCodeFailureEvidence
from .model import (
    PROVIDER_ORDER,
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
    SafeError,
    V2SafeErrorCode,
    SnapshotFreshness,
    CODEX_SOURCE_ID,
    MAX_QUOTA_WINDOWS,
    OPENCODE_SOURCE_ID,
)

_KIND_ORDER = {
    QuotaWindowKind.COMMERCIAL_QUOTA: 0,
    QuotaWindowKind.TECHNICAL_RATE_LIMIT: 1,
    QuotaWindowKind.OTHER: 2,
}
_OPENCODE_FIXED_PERIODS = ("five_hour", "monthly", "weekly")
_FAILURES = {
    "invocation_invalid": ("configuration", "invocation_invalid"),
    "configuration_invalid": ("configuration", "invalid_configuration"),
    "internal_error": ("document", "document_aborted"),
    "guard_acquisition_failed": ("guard_wait", "document_aborted"),
    "guard_wait_timeout": ("guard_wait", "guard_wait_timeout"),
    "deadline_exhausted": ("document", "deadline_exhausted"),
}
_MAX_DOCUMENT_BYTES = 65_536
_MAX_TOOLTIP_SCALARS = 4_096

class _TooManyWindows(ValueError): pass
_NOT_RUN_TEXT = {
    "disabled": "provider disabled",
    "invalid_configuration": "configuration invalid",
    "invocation_invalid": "invocation invalid",
    "document_aborted": "document aborted",
    "guard_wait_timeout": "guard wait timeout",
    "deadline_exhausted": "deadline exhausted",
}
@dataclass(frozen=True, slots=True)
class V2ProjectionInput:
    """Validated document evidence and the providers enabled for this run."""

    document: DocumentView
    enabled_providers: frozenset[ProviderKey] = frozenset()
    opencode_evidence: object | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.document, DocumentView):
            raise TypeError("document must be a DocumentView")
        try:
            enabled = frozenset(ProviderKey(provider) for provider in self.enabled_providers)
        except (TypeError, ValueError):
            raise ValueError("invalid enabled provider set") from None
        object.__setattr__(self, "enabled_providers", enabled)
        if self.opencode_evidence is not None and not isinstance(self.opencode_evidence, OpenCodeFailureEvidence):
            raise ValueError("invalid OpenCode evidence")
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


def _presentation_identity(value: str) -> str:
    if any(character in ";=\\" for character in value):
        return json.dumps(value, ensure_ascii=False)
    return value
def _source(value: object, provider: ProviderKey = ProviderKey.CODEX) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = normalize("NFC", value).strip()
    expected = CODEX_SOURCE_ID if provider is ProviderKey.CODEX else OPENCODE_SOURCE_ID
    return candidate if candidate == expected else None
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
def _window(window: object, provider: ProviderKey = ProviderKey.CODEX) -> dict[str, Any]:
    if not isinstance(window, QuotaWindowView):
        raise ValueError("invalid v2 window")
    kind = _enum(QuotaWindowKind, window.kind, "invalid v2 window kind")
    source_id = _source(window.source_id, provider)
    trusted = source_id is not None
    availability = _enum(QuotaAvailability, window.availability, "invalid v2 availability") if trusted else QuotaAvailability.UNAVAILABLE
    plan_id = None if not trusted or window.plan_id is None else _identity(window.plan_id, "invalid v2 plan id")
    return {
        "kind": kind.value,
        "scope": _identity(window.scope, "invalid v2 scope"),
        "period": _identity(window.period, "invalid v2 period"),
        "plan_id": plan_id,
        "availability": availability.value,
        "source_id": source_id,
        "limit": None if not trusted or window.limit is None else _quantity(window.limit),
        "used": None if not trusted or window.used is None else _quantity(window.used),
        "remaining": None if not trusted or window.remaining is None else _quantity(window.remaining),
        "reset_at": None if not trusted or window.reset_at is None else _timestamp(window.reset_at),
    }


def _opencode_placeholder(period: str, scope: str = "account") -> dict[str, Any]:
    return {"kind": QuotaWindowKind.COMMERCIAL_QUOTA.value, "scope": scope, "period": period, "plan_id": None, "availability": QuotaAvailability.UNAVAILABLE.value, "source_id": None, "limit": None, "used": None, "remaining": None, "reset_at": None}


def _opencode_windows(snapshot: ProviderSnapshotView) -> list[dict[str, Any]]:
    if snapshot.public_state is PublicProviderState.RATE_LIMITED:
        return [
            _window(window, ProviderKey.OPENCODE_GO)
            for window in snapshot.windows
            if isinstance(window, QuotaWindowView) and window.kind is QuotaWindowKind.TECHNICAL_RATE_LIMIT
        ]
    if snapshot.public_state not in (PublicProviderState.AVAILABLE, PublicProviderState.PARTIAL):
        return [_window(window, ProviderKey.OPENCODE_GO) for window in snapshot.windows]

    candidates = {period: [] for period in _OPENCODE_FIXED_PERIODS}
    preserved: list[dict[str, Any]] = []
    for raw in snapshot.windows:
        if not isinstance(raw, QuotaWindowView):
            raise ValueError("invalid v2 window")
        kind = _enum(QuotaWindowKind, raw.kind, "invalid v2 window kind")
        if kind is QuotaWindowKind.COMMERCIAL_QUOTA:
            try:
                period = _identity(raw.period, "invalid v2 period")
            except ValueError:
                continue
            if period in candidates:
                candidates[period].append(raw)
            continue
        preserved.append(_window(raw, ProviderKey.OPENCODE_GO))

    fixed: list[dict[str, Any]] = []
    for period in _OPENCODE_FIXED_PERIODS:
        matches = candidates[period]
        if len(matches) != 1:
            fixed.append(_opencode_placeholder(period))
            continue
        candidate = matches[0]
        try:
            normalized = _window(candidate, ProviderKey.OPENCODE_GO)
        except (TypeError, ValueError):
            normalized = _opencode_placeholder(period)
        if normalized["availability"] != QuotaAvailability.KNOWN.value or normalized["source_id"] != OPENCODE_SOURCE_ID:
            normalized = _opencode_placeholder(period, normalized["scope"])
        fixed.append(normalized)
    return preserved + fixed
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
def _error(code: SafeErrorCode, evidence: object | None = None) -> dict[str, str]:
    code = _enum(SafeErrorCode, code, "invalid v2 error code")
    if evidence is not None:
        if not isinstance(evidence, OpenCodeFailureEvidence):
            raise ValueError("invalid OpenCode evidence")
        mapped = {
            OpenCodeFailureEvidence.CREDENTIAL_INVALID: "credential_invalid",
            OpenCodeFailureEvidence.TIMEOUT: "provider_timeout",
            OpenCodeFailureEvidence.RATE_LIMITED: "provider_rate_limited",
            OpenCodeFailureEvidence.UNAVAILABLE: "provider_unavailable",
        }[evidence]
        return {"code": mapped, "phase": "provider"}
    mapped = {
        SafeErrorCode.TIMEOUT: "provider_timeout",
        SafeErrorCode.INVALID_PROVIDER_DATA: "invalid_provider_data",
        SafeErrorCode.UNKNOWN_PROVIDER_STATE: "unknown_provider_state",
        V2SafeErrorCode.GUARD_WAIT_TIMEOUT: "guard_wait_timeout",
        V2SafeErrorCode.DEADLINE_EXHAUSTED: "deadline_exhausted",
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


def _percentage(window: dict[str, Any]) -> str | None:
    if window["availability"] != QuotaAvailability.KNOWN.value:
        return None
    limit, remaining = window["limit"], window["remaining"]
    if limit is None or remaining is None:
        return None
    if limit["metric"] != remaining["metric"] or limit["unit"] != remaining["unit"]:
        return None
    limit_value, remaining_value = Decimal(limit["value"]), Decimal(remaining["value"])
    if limit_value <= 0 or remaining_value < 0 or remaining_value > limit_value:
        return None
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        value = remaining_value / limit_value * Decimal("100")
    if not Decimal("0") <= value <= Decimal("100"):
        return None
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    rendered = rendered or "0"
    significant_digits = len(rendered.replace(".", "").lstrip("0")) or 1
    if len(rendered) > 128 or significant_digits > 34:
        return None
    return rendered


def _bounded_summary(base: str, qualifier: str) -> str:
    if len(base) + len(qualifier) <= 128:
        return base + qualifier
    return base[: 128 - len(qualifier)] + qualifier
def _evidenced_unit(window: dict[str, Any]) -> str | None:
    units = {
        quantity["unit"]
        for quantity in (window["limit"], window["used"], window["remaining"])
        if quantity is not None
    }
    return next(iter(units)) if len(units) == 1 else None


def _presentation(
    outcome: str,
    windows: list[dict[str, Any]],
    public_state: str | None,
    freshness: str | None,
    reason: str | None = None,
    tooltip_limit: int = _MAX_TOOLTIP_SCALARS,
) -> dict[str, Any]:
    if outcome != ProviderOutcome.SNAPSHOT.value:
        fallback = _fallback(outcome)
        if outcome == ProviderOutcome.NOT_RUN.value and reason in _NOT_RUN_TEXT:
            fallback["tooltip_text"] += f": {_NOT_RUN_TEXT[reason]}"
        return fallback
    ordered_windows = sorted(windows, key=_window_sort_key)
    eligible = [(window, _percentage(window)) for window in ordered_windows]
    eligible = [(window, value) for window, value in eligible if value is not None]
    if eligible:
        selected, percentage = min(eligible, key=lambda candidate: (Decimal(candidate[1]), _window_sort_key(candidate[0])))
        depleted = {
            "kind": selected["kind"],
            "scope": selected["scope"],
            "period": selected["period"],
            "plan_id": selected["plan_id"],
            "unit": selected["remaining"]["unit"],
            "source_id": selected["source_id"],
            "remaining_percentage": percentage,
        }
        value = f"{percentage}% remaining"
        compact_base = f"Quota {value}"
        alternate_base = f"Quota {_presentation_identity(selected['scope'])} / {_presentation_identity(selected['period'])}: {value}"
    else:
        depleted = None
        value = "percentage unavailable"
        compact_base = alternate_base = "Quota percentage unavailable"
    qualifier = f"; state={public_state}; freshness={freshness}"
    compact = _bounded_summary(compact_base, qualifier)
    alternate = _bounded_summary(alternate_base, qualifier)
    lines = [f"State: {public_state}", f"Freshness: {freshness}", f"Quota: {value}"]
    if depleted is None:
        lines.append("No eligible percentage basis")
    for window in ordered_windows:
        percentage = _percentage(window)
        if percentage is not None:
            result = f"{percentage}% remaining"
        elif window["availability"] == QuotaAvailability.KNOWN.value:
            result = "percentage unavailable"
        else:
            result = f"availability={window['availability']}"
        unit = _evidenced_unit(window)
        line = (
            f"Window: kind={window['kind']}; scope={_presentation_identity(window['scope'])}; "
            f"period={_presentation_identity(window['period'])}; "
            f"plan_id={json.dumps(window['plan_id'], ensure_ascii=False)}; "
            f"unit={_presentation_identity(unit) if unit is not None else 'null'}; "
            f"source_id={json.dumps(window['source_id'], ensure_ascii=False)}; result={result}"
        )
        lines.append(line)
        if window["reset_at"] is not None:
            lines.append(f"Reset: {window['reset_at']}")
    prefix_lines = 4 if depleted is None else 3
    tooltip = "\n".join(lines[:prefix_lines])
    for line in lines[prefix_lines:]:
        candidate = line if not tooltip else f"{tooltip}\n{line}"
        if len(candidate) > tooltip_limit:
            break
        tooltip = candidate
    return {"most_depleted_window": depleted, "compact_text": compact, "alternate_text": alternate, "tooltip_text": tooltip}
def _provider(view: ProviderView, enabled: frozenset[ProviderKey], tooltip_limit: int, opencode_evidence: object | None = None) -> tuple[dict[str, Any], str]:
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
            source_id=_source(snapshot.source_id, provider),
        )
        windows = (
            _opencode_windows(snapshot)
            if provider is ProviderKey.OPENCODE_GO
            else [_window(window, provider) for window in snapshot.windows]
        )
        item["windows"] = sorted(windows, key=_window_sort_key)
        if len(item["windows"]) > MAX_QUOTA_WINDOWS:
            raise _TooManyWindows("too many v2 windows")
    elif outcome is ProviderOutcome.UNDETECTED:
        if view.snapshot is not None or view.error is not None:
            raise ValueError("invalid v2 undetected outcome")
    elif outcome is ProviderOutcome.NOT_RUN:
        if view.snapshot is not None or view.error is not None or (provider in enabled and view.not_run_reason not in {"disabled", "document_aborted", "guard_wait_timeout", "deadline_exhausted"}):
            raise ValueError("invalid v2 not-run outcome")
        item["not_run_reason"] = view.not_run_reason or "disabled"
    else:
        if view.snapshot is not None or view.error is None:
            raise ValueError("invalid v2 execution-error outcome")
        item["execution_error"] = _error(view.error.code, opencode_evidence if provider is ProviderKey.OPENCODE_GO else None)
    item.update(_presentation(outcome.value, item["windows"], item["public_state"], item["freshness"], item["not_run_reason"], tooltip_limit))
    return item, outcome.value


def _project_v2_document(input: V2ProjectionInput, tooltip_limit: int) -> dict[str, Any]:
    """Build the ordered JSON-compatible v2 document without encoding it."""

    if not isinstance(input, V2ProjectionInput):
        raise TypeError("input must be a V2ProjectionInput")
    views = {view.provider: view for view in input.document.providers}
    if tuple(views) != PROVIDER_ORDER or len(views) != len(PROVIDER_ORDER):
        raise ValueError("document providers are not canonical")
    providers, outcomes = zip(
        *(
            _provider(
                views[provider],
                input.enabled_providers,
                tooltip_limit,
                input.opencode_evidence if provider is ProviderKey.OPENCODE_GO else None,
            )
            for provider in PROVIDER_ORDER
        )
    )
    successful = {ProviderOutcome.SNAPSHOT.value, ProviderOutcome.UNDETECTED.value}
    document_error = input.document.document_error
    if document_error is not None and document_error.code is V2SafeErrorCode.CLEANUP_FAILED:
        execution_state, execution_error = "execution_error", {"code": "cleanup_failed", "phase": "cleanup"}
    elif document_error is not None and document_error.code in (V2SafeErrorCode.GUARD_WAIT_TIMEOUT, V2SafeErrorCode.DEADLINE_EXHAUSTED):
        execution_state = "not_run"
        execution_error = {"code": document_error.code.value, "phase": "guard_wait" if document_error.code is V2SafeErrorCode.GUARD_WAIT_TIMEOUT else "document"}
    elif document_error is not None:
        execution_state, execution_error = "execution_error", {"code": document_error.code.value, "phase": "guard_wait"}
    elif all(outcome in successful for outcome in outcomes):
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


def project_v2_not_run_bytes(reason: str) -> bytes:
    """Project a document-level not-run matrix entry."""

    if reason not in {"guard_wait_timeout", "deadline_exhausted"}:
        raise ValueError("unsupported v2 not-run reason")
    code = V2SafeErrorCode.GUARD_WAIT_TIMEOUT if reason == "guard_wait_timeout" else V2SafeErrorCode.DEADLINE_EXHAUSTED
    error = SafeError(code)
    document = DocumentView.ordered(
        ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.NOT_RUN, not_run_reason=reason),
        ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.NOT_RUN, not_run_reason=reason),
        error,
    )
    return project_v2_bytes(V2ProjectionInput(document))


def project_v2_document(input: V2ProjectionInput) -> dict[str, Any]:
    """Build the ordered JSON-compatible v2 document without encoding it."""

    return _project_v2_document(input, _MAX_TOOLTIP_SCALARS)
def _encode(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def project_v2_bytes(input: V2ProjectionInput) -> bytes:
    """Return one compact UTF-8 v2 document followed by exactly one LF."""

    try:
        encoded = _encode(project_v2_document(input))
    except _TooManyWindows:
        return project_v2_failure_bytes("internal_error")
    if len(encoded) <= _MAX_DOCUMENT_BYTES:
        return encoded

    low, high, best = 0, _MAX_TOOLTIP_SCALARS, None
    while low <= high:
        tooltip_limit = (low + high) // 2
        candidate = _encode(_project_v2_document(input, tooltip_limit))
        if len(candidate) <= _MAX_DOCUMENT_BYTES:
            best = candidate
            low = tooltip_limit + 1
        else:
            high = tooltip_limit - 1
    return best if best is not None else project_v2_failure_bytes("internal_error")
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
        item.update(_presentation("not_run", [], None, None, reason))
        providers.append(item)
    return _encode(
        {
            "version": 2,
            "execution_state": "execution_error",
            "execution_error": {"code": value, "phase": phase},
            "providers": providers,
        }
    )
