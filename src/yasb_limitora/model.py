"""Closed provider and machine-document view models."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from unicodedata import normalize

SAFE_SOURCE_IDS = frozenset({"codex-app-server-v2", "opencode-go-dashboard"})
MAX_DISPLAY_LABEL_LENGTH = 64
MAX_QUOTA_WINDOWS = 32
MAX_QUANTITY_SIGNIFICANT_DIGITS = 128
MAX_QUANTITY_TEXT_LENGTH = 256

class ProviderKey(str, Enum):
    CODEX = "codex"
    OPENCODE_GO = "opencode_go"

PROVIDER_ORDER = (ProviderKey.CODEX, ProviderKey.OPENCODE_GO)

class ProviderState(str, Enum):
    LOADING = "loading"
    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    SAFE_ERROR = "safe_error"


class ProviderOutcome(str, Enum):
    SNAPSHOT = "snapshot"
    UNDETECTED = "undetected"
    NOT_RUN = "not_run"
    EXECUTION_ERROR = "execution_error"


class PublicProviderState(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    UNAUTHORIZED = "unauthorized"
    RATE_LIMITED = "rate_limited"
    TRANSIENT_ERROR = "transient_error"
    INVALID_DATA = "invalid_data"


class SnapshotFreshness(str, Enum):
    FRESH = "fresh"
    STALE = "stale"


class QuotaWindowKind(str, Enum):
    COMMERCIAL_QUOTA = "commercial_quota"
    TECHNICAL_RATE_LIMIT = "technical_rate_limit"
    OTHER = "other"


class QuotaMetricKind(str, Enum):
    COMMERCIAL_QUOTA = "commercial_quota"
    TECHNICAL_RATE_LIMIT = "technical_rate_limit"


class QuotaAvailability(str, Enum):
    KNOWN = "known"
    UNLIMITED = "unlimited"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"
    NOT_AUTHORIZED = "not_authorized"
    NOT_APPLICABLE = "not_applicable"
    INVALID = "invalid"
    ERROR = "error"

class SafeErrorCode(str, Enum):
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"
    INTERNAL_ERROR = "internal_error"
    CONFIGURATION_INVALID = "configuration_invalid"
    INVOCATION_INVALID = "invocation_invalid"
    INVALID_PROVIDER_DATA = "invalid_provider_data"
    UNKNOWN_PROVIDER_STATE = "unknown_provider_state"


class V2SafeErrorCode(str, Enum):
    """Document/provider error codes added without changing the v1 enum."""

    GUARD_ACQUISITION_FAILED = "guard_acquisition_failed"
    GUARD_WAIT_TIMEOUT = "guard_wait_timeout"
    DEADLINE_EXHAUSTED = "deadline_exhausted"
    CLEANUP_FAILED = "cleanup_failed"

def _enum(enum: type[Enum], value: object, message: str) -> Enum:
    try:
        return enum(value)
    except (TypeError, ValueError):
        raise ValueError(message) from None

def _label(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > MAX_DISPLAY_LABEL_LENGTH or any(ord(char) < 32 for char in value):
        raise ValueError("invalid provider label") from None
    return value


def canonical_identity(value: object, message: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(message) from None
    value = normalize("NFC", value)
    if len(value) > 64:
        raise ValueError(message) from None
    if any(
        ord(char) <= 0x1F
        or ord(char) == 0x7F
        or 0xD800 <= ord(char) <= 0xDFFF
        for char in value
    ):
        raise ValueError(message) from None
    return value


def _aware(value: object, message: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(message) from None
    return value


def _canonical_decimal(value: object) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError("invalid quota quantity") from None
    if value.is_zero():
        return Decimal("0")
    _, digits, exponent = value.as_tuple()
    while digits[-1] == 0:
        digits = digits[:-1]
        exponent += 1
    position = len(digits) + exponent
    rendered_length = (
        2 - position + len(digits)
        if position <= 0
        else position
        if position >= len(digits)
        else len(digits) + 1
    )
    if len(digits) > MAX_QUANTITY_SIGNIFICANT_DIGITS or rendered_length > MAX_QUANTITY_TEXT_LENGTH:
        raise ValueError("quota quantity exceeds canonical limits") from None
    fixed = format(Decimal((0, digits, exponent)), "f")
    canonical = fixed.rstrip("0").rstrip(".") if "." in fixed else fixed
    if len(canonical) > MAX_QUANTITY_TEXT_LENGTH:
        raise ValueError("quota quantity exceeds canonical limits") from None
    return Decimal(canonical)


def _parse_canonical_decimal(value: object) -> Decimal:
    if type(value) is not str or not value or len(value) > MAX_QUANTITY_TEXT_LENGTH:
        raise ValueError("invalid quota quantity") from None
    try:
        value.encode("ascii")
        parsed = Decimal(value)
    except (ArithmeticError, UnicodeEncodeError, ValueError):
        raise ValueError("invalid quota quantity") from None
    canonical = _canonical_decimal(parsed)
    if format(canonical, "f") != value:
        raise ValueError("invalid quota quantity") from None
    return canonical


def _source_id(value: object) -> str | None:
    if value is not None and (not isinstance(value, str) or value not in SAFE_SOURCE_IDS):
        raise ValueError("invalid source id") from None
    return value

@dataclass(frozen=True, slots=True)
class SafeError:
    code: SafeErrorCode | V2SafeErrorCode

    def __post_init__(self) -> None:
        try:
            code = _enum(SafeErrorCode, self.code, "invalid safe error code")
        except ValueError:
            code = _enum(V2SafeErrorCode, self.code, "invalid safe error code")
        object.__setattr__(self, "code", code)


@dataclass(frozen=True, slots=True)
class QuotaQuantity:
    value: Decimal
    metric: QuotaMetricKind
    unit: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _canonical_decimal(self.value))
        object.__setattr__(self, "metric", _enum(QuotaMetricKind, self.metric, "invalid quota metric"))
        object.__setattr__(self, "unit", canonical_identity(self.unit, "invalid quota unit"))


@dataclass(frozen=True, slots=True)
class QuotaWindowView:
    kind: QuotaWindowKind
    scope: str
    period: str
    plan_id: str | None
    availability: QuotaAvailability
    source_id: str | None
    limit: QuotaQuantity | None = None
    used: QuotaQuantity | None = None
    remaining: QuotaQuantity | None = None
    reset_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _enum(QuotaWindowKind, self.kind, "invalid quota window kind"))
        object.__setattr__(self, "availability", _enum(QuotaAvailability, self.availability, "invalid quota availability"))
        object.__setattr__(self, "scope", canonical_identity(self.scope, "invalid quota scope"))
        object.__setattr__(self, "period", canonical_identity(self.period, "invalid quota period"))
        if self.plan_id is not None:
            object.__setattr__(self, "plan_id", canonical_identity(self.plan_id, "invalid quota plan id"))
        object.__setattr__(self, "source_id", _source_id(self.source_id))
        for quantity in (self.limit, self.used, self.remaining):
            if quantity is not None and not isinstance(quantity, QuotaQuantity):
                raise ValueError("invalid quota quantity") from None
        if self.reset_at is not None:
            _aware(self.reset_at, "invalid quota reset timestamp")
        values = tuple(quantity for quantity in (self.limit, self.used, self.remaining) if quantity is not None)
        if self.availability is QuotaAvailability.KNOWN:
            if not values:
                raise ValueError("known quota window requires a quantity")
            expected = None if self.kind is QuotaWindowKind.OTHER else QuotaMetricKind(self.kind.value)
            if expected is not None and any(quantity.metric is not expected for quantity in values):
                raise ValueError("quota quantities must match their window kind")
            if len({(quantity.metric, quantity.unit) for quantity in values}) != 1:
                raise ValueError("quota quantities must use the same metric and unit")
            if self.limit is not None:
                if self.used is not None and self.used.value > self.limit.value:
                    raise ValueError("used quota cannot exceed limit")
                if self.remaining is not None and self.remaining.value > self.limit.value:
                    raise ValueError("remaining quota cannot exceed limit")
                if self.used is not None and self.remaining is not None and self.used.value + self.remaining.value != self.limit.value:
                    raise ValueError("used and remaining quota must equal limit")
        elif values or self.reset_at is not None:
            raise ValueError("non-known quota cannot contain numeric values or a reset")


@dataclass(frozen=True, slots=True)
class ProviderSnapshotView:
    public_state: PublicProviderState
    freshness: SnapshotFreshness
    status_observed_at: datetime
    fetched_at: datetime
    data_at: datetime
    source_id: str | None
    windows: tuple[QuotaWindowView, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "public_state", _enum(PublicProviderState, self.public_state, "invalid public provider state"))
        object.__setattr__(self, "freshness", _enum(SnapshotFreshness, self.freshness, "invalid snapshot freshness"))
        _aware(self.status_observed_at, "invalid status timestamp")
        _aware(self.fetched_at, "invalid fetched timestamp")
        _aware(self.data_at, "invalid data timestamp")
        if self.status_observed_at > self.fetched_at or self.data_at > self.fetched_at:
            raise ValueError("snapshot timestamps cannot be newer than fetched_at")
        object.__setattr__(self, "source_id", _source_id(self.source_id))
        if not isinstance(self.windows, tuple) or not all(isinstance(window, QuotaWindowView) for window in self.windows):
            raise TypeError("windows must contain immutable quota window values")
        if len(self.windows) > MAX_QUOTA_WINDOWS:
            raise ValueError("snapshot contains too many quota windows")
        identities = tuple((window.kind, window.scope, window.period) for window in self.windows)
        if len(set(identities)) != len(identities):
            raise ValueError("snapshot cannot contain ambiguous quota windows")
        if self.public_state is PublicProviderState.RATE_LIMITED and any(
            window.kind is not QuotaWindowKind.TECHNICAL_RATE_LIMIT for window in self.windows
        ):
            raise ValueError("rate-limited snapshots can only contain technical windows")


def _legacy_state_for_snapshot(snapshot: ProviderSnapshotView) -> ProviderState:
    if snapshot.freshness is SnapshotFreshness.STALE:
        return ProviderState.UNAVAILABLE
    if snapshot.public_state is PublicProviderState.AVAILABLE:
        return ProviderState.SUCCESS
    if snapshot.public_state is PublicProviderState.UNAVAILABLE:
        return ProviderState.UNAVAILABLE
    return ProviderState.SUCCESS if snapshot.public_state is PublicProviderState.PARTIAL else ProviderState.UNAVAILABLE

@dataclass(frozen=True, slots=True)
class ProviderView:
    provider: ProviderKey
    state: ProviderState
    error: SafeError | None = None
    display_label: str | None = None
    outcome: ProviderOutcome | None = None
    snapshot: ProviderSnapshotView | None = None
    not_run_reason: str | None = None

    def __post_init__(self) -> None:
        provider = _enum(ProviderKey, self.provider, "invalid provider key")
        state = _enum(ProviderState, self.state, "invalid provider state")
        if self.error is not None and not isinstance(self.error, SafeError):
            raise ValueError("invalid provider error") from None
        if state is ProviderState.SAFE_ERROR and self.error is None:
            raise ValueError("safe_error requires a safe error code")
        if state is not ProviderState.SAFE_ERROR and self.error is not None:
            raise ValueError("only safe_error may carry an error code")
        if self.outcome is not None:
            outcome = _enum(ProviderOutcome, self.outcome, "invalid provider outcome")
            if outcome is ProviderOutcome.SNAPSHOT and self.snapshot is None:
                raise ValueError("snapshot outcome requires a snapshot")
            if self.snapshot is not None and not isinstance(self.snapshot, ProviderSnapshotView):
                raise ValueError("invalid provider snapshot") from None
            if outcome is ProviderOutcome.SNAPSHOT and (
                state is ProviderState.SAFE_ERROR or self.error is not None
            ):
                raise ValueError("snapshot cannot carry an execution error") from None
            if outcome is not ProviderOutcome.SNAPSHOT and self.snapshot is not None:
                raise ValueError("only snapshot outcome may carry a snapshot")
            if outcome is ProviderOutcome.EXECUTION_ERROR and state is not ProviderState.SAFE_ERROR:
                raise ValueError("execution_error requires safe_error state")
            if outcome is not ProviderOutcome.EXECUTION_ERROR and self.error is not None and outcome is not ProviderOutcome.SNAPSHOT:
                raise ValueError("only execution_error may carry an error code")
            object.__setattr__(self, "outcome", outcome)
        elif self.snapshot is not None:
            raise ValueError("snapshot requires a snapshot outcome")
        object.__setattr__(self, "display_label", _label(self.display_label))
        if self.not_run_reason is not None and self.outcome is not ProviderOutcome.NOT_RUN:
            raise ValueError("only not_run may carry a not-run reason")
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "state", state)

@dataclass(frozen=True, slots=True)
class DocumentView:
    providers: tuple[ProviderView, ...]
    document_error: SafeError | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.providers, tuple):
            raise TypeError("providers must be an immutable tuple")
        if not all(isinstance(view, ProviderView) for view in self.providers):
            raise TypeError("providers must contain ProviderView values")
        if tuple(view.provider for view in self.providers) != PROVIDER_ORDER:
            raise ValueError("providers must be ordered codex, opencode_go")
        if self.document_error is not None and not isinstance(self.document_error, SafeError):
            raise ValueError("invalid document error")

    @classmethod
    def ordered(cls, codex: ProviderView, opencode_go: ProviderView, document_error: SafeError | None = None) -> "DocumentView":
        return cls((codex, opencode_go), document_error)
