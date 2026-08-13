"""Independent, bounded coordination of the two provider views."""

from __future__ import annotations

import math
import os
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable

from .codex_helper import CodexHelperExecutor
from .config import ConfigError, LocalConfig
from .limitora_api import AUTH_COOKIE_ENV, read_opencode_go
from .model import DocumentView, ProviderKey, ProviderState, ProviderView, SafeError, SafeErrorCode


def _error(provider: ProviderKey, code: SafeErrorCode) -> ProviderView:
    return ProviderView(provider, ProviderState.SAFE_ERROR, SafeError(code))


def _unavailable(provider: ProviderKey) -> ProviderView:
    return ProviderView(provider, ProviderState.UNAVAILABLE)


@dataclass
class _Invocation:
    provider: ProviderKey
    function: Callable[[], ProviderView]
    timeout_seconds: float
    result: ProviderView | None = None
    finished: bool = False
    expired: bool = False

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._execute, daemon=True)

    def start(self) -> None:
        self._deadline = time.monotonic() + self.timeout_seconds
        self._thread.start()

    def _execute(self) -> None:
        try:
            result = self.function()
        except Exception as error:  # noqa: BLE001 - provider failures are projected safely
            result = _error(
                self.provider,
                SafeErrorCode.TIMEOUT
                if isinstance(error, TimeoutError)
                else SafeErrorCode.CONFIGURATION_INVALID
                if isinstance(error, (ConfigError, TypeError, ValueError))
                else SafeErrorCode.PROVIDER_ERROR,
            )
        timed_out = time.monotonic() > self._deadline
        with self._lock:
            if not self.expired and not timed_out:
                self.result = result
            else:
                self.expired = True
            self.finished = True

    def finish(self, timeout_seconds: float) -> ProviderView:
        self._thread.join(max(0.0, self._deadline - time.monotonic()))
        with self._lock:
            if self.expired:
                return _error(self.provider, SafeErrorCode.TIMEOUT)
            if self.finished and self.result is not None:
                if isinstance(self.result, ProviderView) and self.result.provider is self.provider:
                    return self.result
                return _error(self.provider, SafeErrorCode.INTERNAL_ERROR)
            self.expired = True
            return _error(self.provider, SafeErrorCode.TIMEOUT)


class RuntimeCoordinator:
    """Run Codex and OpenCode Go independently without shared result state."""

    def __init__(
        self,
        codex_executor: Any | None = None,
        opencode_reader: Callable[[str, Mapping[str, str]], ProviderView] = read_opencode_go,
    ) -> None:
        self._codex = codex_executor if codex_executor is not None else CodexHelperExecutor()
        self._opencode_reader = opencode_reader

    def run(
        self,
        config: LocalConfig,
        environment: Mapping[str, str] | None = None,
    ) -> DocumentView:
        if not isinstance(config, LocalConfig):
            raise ConfigError("invalid local configuration")
        environment = os.environ if environment is None else environment
        calls: dict[ProviderKey, _Invocation] = {}
        views: dict[ProviderKey, ProviderView] = {}

        if not config.codex.enabled or config.codex.runner is None:
            views[ProviderKey.CODEX] = _unavailable(ProviderKey.CODEX)
        else:
            runner = config.codex.runner
            executor = self._codex
            calls[ProviderKey.CODEX] = _Invocation(
                ProviderKey.CODEX, lambda: executor.run((runner, "app-server")), config.codex.timeout_seconds
            )

        workspace = config.opencode_go.workspace_id
        cookie = environment.get(AUTH_COOKIE_ENV)
        if (
            not config.opencode_go.enabled
            or not isinstance(workspace, str)
            or not workspace
            or not isinstance(cookie, str)
            or not cookie
        ):
            views[ProviderKey.OPENCODE_GO] = _unavailable(ProviderKey.OPENCODE_GO)
        else:
            calls[ProviderKey.OPENCODE_GO] = _Invocation(
                ProviderKey.OPENCODE_GO,
                lambda: self._opencode_reader(workspace, environment),
                config.opencode_go.timeout_seconds,
            )

        timeouts = (config.codex.timeout_seconds, config.opencode_go.timeout_seconds)
        if not all(math.isfinite(timeout) and timeout > 0 for timeout in timeouts):
            error = SafeErrorCode.CONFIGURATION_INVALID
            return DocumentView.ordered(_error(ProviderKey.CODEX, error), _error(ProviderKey.OPENCODE_GO, error))
        for call in calls.values():
            call.start()
        for provider, call in calls.items():
            views[provider] = call.finish(timeouts[provider is ProviderKey.OPENCODE_GO])
        return DocumentView.ordered(views[ProviderKey.CODEX], views[ProviderKey.OPENCODE_GO])


ProviderCoordinator = RuntimeCoordinator


def coordinate(
    config: LocalConfig,
    environment: Mapping[str, str] | None = None,
    *,
    codex_executor: Any | None = None,
    opencode_reader: Callable[[str, Mapping[str, str]], ProviderView] = read_opencode_go,
) -> DocumentView:
    return RuntimeCoordinator(codex_executor, opencode_reader).run(config, environment)


__all__ = ("ProviderCoordinator", "RuntimeCoordinator", "coordinate")
