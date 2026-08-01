"""Deterministic provider/executor fakes with no network or process behavior."""
from dataclasses import dataclass
from typing import Protocol
import math
from ..model import DocumentView, ProviderKey, ProviderState, ProviderView, SafeError, SafeErrorCode
class ProviderExecutor(Protocol):
    def execute(self, provider: ProviderKey, timeout_seconds: float) -> ProviderView: ...
@dataclass(frozen=True, slots=True)
class ScriptedOutcome:
    view: ProviderView
    delay_seconds: float = 0.0
    late: bool = False
    def __post_init__(self) -> None:
        if not isinstance(self.view, ProviderView) or not math.isfinite(self.delay_seconds) or self.delay_seconds < 0:
            raise ValueError("invalid scripted outcome")
@dataclass(frozen=True, slots=True)
class ScriptedProviderExecutor:
    """Two explicit provider scripts; no registry or mutable completion state."""
    codex: ScriptedOutcome | None
    opencode_go: ScriptedOutcome | None
    def execute(self, provider: ProviderKey, timeout_seconds: float) -> ProviderView:
        if not isinstance(provider, ProviderKey) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("invalid executor request")
        outcome = self.codex if provider is ProviderKey.CODEX else self.opencode_go if provider is ProviderKey.OPENCODE_GO else None
        if outcome is None:
            return ProviderView(provider, ProviderState.UNAVAILABLE)
        if outcome.view.provider is not provider:
            raise ValueError("scripted provider mismatch")
        if outcome.late or outcome.delay_seconds > timeout_seconds:
            return ProviderView(provider, ProviderState.SAFE_ERROR, SafeError(SafeErrorCode.TIMEOUT))
        return outcome.view
    def execute_all(self, timeout_seconds: float) -> DocumentView:
        return DocumentView.ordered(
            self.execute(ProviderKey.CODEX, timeout_seconds),
            self.execute(ProviderKey.OPENCODE_GO, timeout_seconds),
        )
