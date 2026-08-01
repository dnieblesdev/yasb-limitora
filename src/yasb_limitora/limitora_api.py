"""The narrow, root-public Limitora 0.1.0 adapter boundary."""

from collections.abc import Mapping, Sequence
from datetime import timedelta
from decimal import Decimal
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
    SAFE_SOURCE_IDS,
    SnapshotFreshness,
    ProviderView,
    SafeError,
    SafeErrorCode,
    _legacy_state_for_snapshot,
    canonical_identity,
)

AUTH_COOKIE_ENV = "LIMITORA_AUTH_COOKIE"
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


def _safe_source(source: object) -> str | None:
    reference = getattr(source, "reference", None)
    if not isinstance(reference, str):
        return None
    candidate = normalize("NFC", reference).strip()
    return candidate if candidate in SAFE_SOURCE_IDS else None


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


def _window(window: object) -> QuotaWindowView:
    if not isinstance(window, QuotaWindow):
        raise ValueError("invalid provider quota window") from None
    if not isinstance(window.kind, WindowKind) or not isinstance(window.availability, ValueAvailability):
        raise ValueError("invalid provider quota window") from None
    try:
        kind = QuotaWindowKind(window.kind.value)
        availability = QuotaAvailability(window.availability.value)
    except (TypeError, ValueError):
        raise ValueError("invalid provider quota window") from None
    return QuotaWindowView(
        kind=kind,
        scope=canonical_identity(window.scope, "invalid provider scope"),
        period=canonical_identity(window.period, "invalid provider period"),
        plan_id=None if window.plan_id is None else canonical_identity(window.plan_id, "invalid provider plan id"),
        availability=availability,
        source_id=_safe_source(window.source),
        limit=_quantity(window.limit),
        used=_quantity(window.used),
        remaining=_quantity(window.remaining),
        reset_at=window.reset_at,
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
    windows = tuple(_window(window) for window in snapshot.quota_windows)
    view = ProviderSnapshotView(
        public_state=public_state,
        freshness=SnapshotFreshness(result.freshness.value),
        status_observed_at=snapshot.status.observed_at,
        fetched_at=snapshot.fetched_at,
        data_at=snapshot.data_at,
        source_id=_safe_source(snapshot.source),
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


def _read(provider: ProviderKey, client: StatusClient) -> ProviderView:
    try:
        result = client.read_status(_REQUEST)
    except TimeoutError:
        return _error(provider, SafeErrorCode.TIMEOUT)
    except ProviderError:
        return _error(provider, SafeErrorCode.PROVIDER_ERROR)
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


def read_opencode_go(
    workspace_id: str, environment: Mapping[str, str]
) -> ProviderView:
    cookie = environment.get(AUTH_COOKIE_ENV)
    if not isinstance(cookie, str) or not cookie or not isinstance(workspace_id, str) or not workspace_id:
        return ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.NOT_RUN)
    try:
        client = activate_provider(OpenCodeGoConfig(workspace_id, cookie))
    except (CompositionError, TypeError, ValueError):
        return _error(ProviderKey.OPENCODE_GO, SafeErrorCode.CONFIGURATION_INVALID)
    except Exception:  # noqa: BLE001 - construction failures are redacted
        return _error(ProviderKey.OPENCODE_GO, SafeErrorCode.INTERNAL_ERROR)
    return _read(ProviderKey.OPENCODE_GO, client)


__all__ = ("AUTH_COOKIE_ENV", "CodexLimitoraAdapter", "read_codex", "read_opencode_go")
