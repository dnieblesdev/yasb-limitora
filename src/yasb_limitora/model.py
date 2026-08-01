"""Closed provider and machine-document view models."""

from dataclasses import dataclass
from enum import Enum

class ProviderKey(str, Enum):
    CODEX = "codex"
    OPENCODE_GO = "opencode_go"

PROVIDER_ORDER = (ProviderKey.CODEX, ProviderKey.OPENCODE_GO)

class ProviderState(str, Enum):
    LOADING = "loading"
    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    SAFE_ERROR = "safe_error"

class SafeErrorCode(str, Enum):
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"
    INTERNAL_ERROR = "internal_error"
    CONFIGURATION_INVALID = "configuration_invalid"
    INVOCATION_INVALID = "invocation_invalid"

def _enum(enum: type[Enum], value: object, message: str) -> Enum:
    try:
        return enum(value)
    except (TypeError, ValueError):
        raise ValueError(message) from None

def _label(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > 64 or any(ord(char) < 32 for char in value):
        raise ValueError("invalid provider label") from None
    return value

@dataclass(frozen=True, slots=True)
class SafeError:
    code: SafeErrorCode

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _enum(SafeErrorCode, self.code, "invalid safe error code"))

@dataclass(frozen=True, slots=True)
class ProviderView:
    provider: ProviderKey
    state: ProviderState
    error: SafeError | None = None
    display_label: str | None = None

    def __post_init__(self) -> None:
        provider = _enum(ProviderKey, self.provider, "invalid provider key")
        state = _enum(ProviderState, self.state, "invalid provider state")
        if self.error is not None and not isinstance(self.error, SafeError):
            raise ValueError("invalid provider error") from None
        if state is ProviderState.SAFE_ERROR and self.error is None:
            raise ValueError("safe_error requires a safe error code")
        if state is not ProviderState.SAFE_ERROR and self.error is not None:
            raise ValueError("only safe_error may carry an error code")
        object.__setattr__(self, "display_label", _label(self.display_label))
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "state", state)

@dataclass(frozen=True, slots=True)
class DocumentView:
    providers: tuple[ProviderView, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.providers, tuple):
            raise TypeError("providers must be an immutable tuple")
        if not all(isinstance(view, ProviderView) for view in self.providers):
            raise TypeError("providers must contain ProviderView values")
        if tuple(view.provider for view in self.providers) != PROVIDER_ORDER:
            raise ValueError("providers must be ordered codex, opencode_go")

    @classmethod
    def ordered(cls, codex: ProviderView, opencode_go: ProviderView) -> "DocumentView":
        return cls((codex, opencode_go))
