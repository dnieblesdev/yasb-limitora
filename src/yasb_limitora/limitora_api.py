"""The narrow, root-public Limitora 0.2.0 adapter boundary."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from enum import Enum
from unicodedata import normalize

from limitora import (
    AuthorizationPolicy,
    CodexJsonlConfig,
    CompositionError,
    Freshness,
    FreshnessPolicy,
    MetricKind,
    OpenCodeGoConfig,
    ProviderError,
    ProviderErrorKind,
    StatusClient,
    StatusRequest,
    StatusSnapshotResult,
    StatusUndetectedResult,
    activate_provider,
)
from limitora import ProviderState as LimitoraProviderState
from limitora.models import (
    MetricKind as LimitoraMetricKind,
    ProviderId,
    ProviderSnapshot,
    ProviderStatus,
    Quantity,
    QuotaWindow,
    SourceMetadata,
    ValueAvailability,
    WindowKind,
)

from .model import (
    ProviderKey,
    ProviderOutcome,
    ProviderSnapshotView,
    ProviderState,
    PublicProviderState,
    QuotaAvailability,
    QuotaMetricKind,
    QuotaQuantity,
    QuotaWindowKind,
    QuotaWindowView,
    SnapshotFreshness,
    ProviderView,
    SafeError,
    SafeErrorCode,
    CODEX_SOURCE_ID,
    OPENCODE_SOURCE_ID,
    _legacy_state_for_snapshot,
    canonical_identity,
)

OPENCODE_API_KEY_ENV = "LIMITORA_OPENCODE_API_KEY"
_TRANSPORT_TIMEOUT_MESSAGES = {"HTTP request timed out", "OpenCode Go request timed out", "OpenCode Go request budget expired"}
_REQUEST = StatusRequest(
    frozenset({MetricKind.COMMERCIAL_QUOTA}),
    AuthorizationPolicy.ALLOW_AUTHORIZED_SOURCE,
    FreshnessPolicy(timedelta(seconds=10)),
)


class _UnknownProviderState(ValueError):
    pass


def _error(provider: ProviderKey, code: SafeErrorCode) -> ProviderView:
    return ProviderView(
        provider,
        ProviderState.SAFE_ERROR,
        SafeError(code),
        outcome=ProviderOutcome.EXECUTION_ERROR,
    )


@dataclass(frozen=True, slots=True)
class OpenCodeRequest:
    api_key: str
    timeout_seconds: float
    deadline_seconds: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.api_key, str) or not self.api_key:
            raise ValueError("invalid OpenCode API key")
        if not isinstance(self.timeout_seconds, (int, float)) or isinstance(self.timeout_seconds, bool) or not 0 < self.timeout_seconds <= 10:
            raise ValueError("invalid OpenCode timeout")
        if self.deadline_seconds is not None and (not isinstance(self.deadline_seconds, (int, float)) or isinstance(self.deadline_seconds, bool) or self.deadline_seconds <= 0):
            raise ValueError("invalid OpenCode deadline")

    def __repr__(self) -> str:
        return f"OpenCodeRequest(timeout_seconds={self.timeout_seconds!r}, deadline_seconds={self.deadline_seconds!r})"

    __str__ = __repr__


class OpenCodeFailureEvidence(str, Enum):
    CREDENTIAL_INVALID = "credential_invalid"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
@dataclass(frozen=True, slots=True)
class OpenCodeReadResult:
    view: ProviderView
    evidence: OpenCodeFailureEvidence | None = None

    def __repr__(self) -> str:
        return f"OpenCodeReadResult(view={self.view!r})"

    __str__ = __repr__


def _safe_source(source: object, provider: ProviderKey = ProviderKey.CODEX) -> str | None:
    reference = getattr(source, "reference", None)
    if not isinstance(reference, str):
        return None
    candidate = normalize("NFC", reference).strip()
    expected = CODEX_SOURCE_ID if provider is ProviderKey.CODEX else OPENCODE_SOURCE_ID
    return candidate if candidate == expected else None


def _quantity(quantity: object) -> QuotaQuantity | None:
    if quantity is None:
        return None
    if not isinstance(quantity, Quantity):
        raise ValueError("invalid provider quantity") from None
    if not isinstance(quantity.metric, LimitoraMetricKind):
        raise ValueError("invalid provider metric") from None
    try:
        metric = QuotaMetricKind(quantity.metric.value)
    except (TypeError, ValueError):
        raise ValueError("unsupported provider metric") from None
    if not isinstance(quantity.value, Decimal) or not quantity.value.is_finite() or quantity.value < 0:
        raise ValueError("invalid provider quantity") from None
    return QuotaQuantity(quantity.value, metric, canonical_identity(quantity.unit, "invalid provider unit"))


def _window(window: object, provider: ProviderKey = ProviderKey.CODEX) -> QuotaWindowView:
    if not isinstance(window, QuotaWindow):
        raise ValueError("invalid provider quota window") from None
    source_id = _safe_source(window.source, provider)
    trusted = source_id is not None
    if not isinstance(window.kind, WindowKind):
        raise ValueError("invalid provider quota window") from None
    try:
        kind = QuotaWindowKind(window.kind.value)
    except (TypeError, ValueError):
        raise ValueError("invalid provider quota window") from None
    if trusted:
        if not isinstance(window.availability, ValueAvailability):
            raise ValueError("invalid provider quota window") from None
        try:
            availability = QuotaAvailability(window.availability.value)
        except (TypeError, ValueError):
            raise ValueError("invalid provider quota window") from None
    else:
        availability = QuotaAvailability.UNAVAILABLE
    return QuotaWindowView(
        kind=kind,
        scope=canonical_identity(window.scope, "invalid provider scope"),
        period=canonical_identity(window.period, "invalid provider period"),
        plan_id=None if not trusted or window.plan_id is None else canonical_identity(window.plan_id, "invalid provider plan id"),
        availability=availability,
        source_id=source_id,
        limit=_quantity(window.limit) if trusted else None,
        used=_quantity(window.used) if trusted else None,
        remaining=_quantity(window.remaining) if trusted else None,
        reset_at=window.reset_at if trusted else None,
    )


def _snapshot(provider: ProviderKey, result: StatusSnapshotResult) -> tuple[PublicProviderState, ProviderSnapshotView]:
    snapshot = result.snapshot
    if not isinstance(snapshot, ProviderSnapshot) or not isinstance(snapshot.provider_id, ProviderId):
        raise ValueError("invalid provider snapshot") from None
    if not isinstance(snapshot.status, ProviderStatus) or not isinstance(snapshot.status.provider_id, ProviderId):
        raise ValueError("invalid provider status") from None
    if not isinstance(snapshot.source, SourceMetadata):
        raise ValueError("invalid provider source") from None
    expected_provider = "codex" if provider is ProviderKey.CODEX else "opencode-go"
    if snapshot.provider_id.value != expected_provider or snapshot.status.provider_id != snapshot.provider_id:
        raise ValueError("provider snapshot identity mismatch") from None
    if not isinstance(snapshot.status.state, LimitoraProviderState):
        raise _UnknownProviderState
    try:
        public_state = PublicProviderState(snapshot.status.state.value)
    except (TypeError, ValueError):
        raise _UnknownProviderState from None
    if not isinstance(result.freshness, Freshness) or not isinstance(snapshot.quota_windows, tuple):
        raise ValueError("invalid provider snapshot metadata") from None
    windows = tuple(_window(window, provider) for window in snapshot.quota_windows)
    view = ProviderSnapshotView(
        public_state=public_state,
        freshness=SnapshotFreshness(result.freshness.value),
        status_observed_at=snapshot.status.observed_at,
        fetched_at=snapshot.fetched_at,
        data_at=snapshot.data_at,
        source_id=_safe_source(snapshot.source, provider),
        windows=windows,
    )
    return public_state, view


def _snapshot_view(provider: ProviderKey, result: StatusSnapshotResult) -> ProviderView:
    try:
        _, snapshot = _snapshot(provider, result)
    except _UnknownProviderState:
        return _error(provider, SafeErrorCode.UNKNOWN_PROVIDER_STATE)
    except (TypeError, ValueError):
        return _error(provider, SafeErrorCode.INVALID_PROVIDER_DATA)
    return ProviderView(
        provider,
        _legacy_state_for_snapshot(snapshot),
        outcome=ProviderOutcome.SNAPSHOT,
        snapshot=snapshot,
    )


_FAILURE_EVIDENCE = {ProviderErrorKind.UNAUTHORIZED: OpenCodeFailureEvidence.CREDENTIAL_INVALID, ProviderErrorKind.RATE_LIMITED: OpenCodeFailureEvidence.RATE_LIMITED}
def _failure_evidence(error: ProviderError) -> OpenCodeFailureEvidence:
    return OpenCodeFailureEvidence.TIMEOUT if error.kind is ProviderErrorKind.TRANSPORT and error.safe_message in _TRANSPORT_TIMEOUT_MESSAGES else _FAILURE_EVIDENCE.get(error.kind, OpenCodeFailureEvidence.UNAVAILABLE)


def _read(provider: ProviderKey, client: StatusClient, evidence: list[OpenCodeFailureEvidence] | None = None) -> ProviderView:
    try:
        result = client.read_status(_REQUEST)
    except TimeoutError:
        if evidence is not None: evidence.append(OpenCodeFailureEvidence.TIMEOUT)
        return _error(provider, SafeErrorCode.TIMEOUT)
    except ProviderError as error:
        code = SafeErrorCode.TIMEOUT if error.kind is ProviderErrorKind.TRANSPORT and error.safe_message in _TRANSPORT_TIMEOUT_MESSAGES else SafeErrorCode.PROVIDER_ERROR
        if evidence is not None:
            evidence.append(_failure_evidence(error))
        return _error(provider, code)
    except (CompositionError, TypeError, ValueError):
        return _error(provider, SafeErrorCode.CONFIGURATION_INVALID)
    except Exception:  # noqa: BLE001 - unknown provider failures are redacted
        return _error(provider, SafeErrorCode.INTERNAL_ERROR)
    if isinstance(result, StatusUndetectedResult):
        return ProviderView(provider, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.UNDETECTED)
    if not isinstance(result, StatusSnapshotResult):
        return _error(provider, SafeErrorCode.INTERNAL_ERROR)
    return _snapshot_view(provider, result)


class CodexLimitoraAdapter:
    """Construct and read one Codex client through the released root API."""

    def __init__(self, activate=activate_provider) -> None:
        self._activate = activate

    def read(self, runner: Sequence[str]) -> ProviderView:
        try:
            client = self._activate(CodexJsonlConfig(tuple(runner)))
        except (CompositionError, TypeError, ValueError):
            return _error(ProviderKey.CODEX, SafeErrorCode.CONFIGURATION_INVALID)
        except Exception:  # noqa: BLE001 - construction failures are redacted
            return _error(ProviderKey.CODEX, SafeErrorCode.INTERNAL_ERROR)
        return _read(ProviderKey.CODEX, client)


def read_codex(runner: Sequence[str]) -> ProviderView:
    return CodexLimitoraAdapter().read(runner)


def read_opencode_go(request: OpenCodeRequest) -> OpenCodeReadResult:
    if not isinstance(request, OpenCodeRequest) or not isinstance(request.api_key, str) or not request.api_key:
        return OpenCodeReadResult(ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.NOT_RUN, not_run_reason="disabled"))
    try:
        client = activate_provider(OpenCodeGoConfig(api_key=request.api_key, timeout=timedelta(seconds=request.timeout_seconds)))
    except (CompositionError, TypeError, ValueError):
        return OpenCodeReadResult(_error(ProviderKey.OPENCODE_GO, SafeErrorCode.CONFIGURATION_INVALID))
    except Exception:  # noqa: BLE001 - construction failures are redacted
        return OpenCodeReadResult(_error(ProviderKey.OPENCODE_GO, SafeErrorCode.INTERNAL_ERROR))
    evidence: list[OpenCodeFailureEvidence] = []
    return OpenCodeReadResult(_read(ProviderKey.OPENCODE_GO, client, evidence), evidence[0] if evidence else None)


__all__ = ("OPENCODE_API_KEY_ENV", "CodexLimitoraAdapter", "OpenCodeReadResult", "OpenCodeRequest", "read_codex", "read_opencode_go")
