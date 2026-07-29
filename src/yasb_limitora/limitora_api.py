"""The narrow, root-public Limitora 0.1.0 adapter boundary."""

from collections.abc import Mapping, Sequence
from datetime import timedelta

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

from .model import ProviderKey, ProviderState, ProviderView, SafeError, SafeErrorCode

AUTH_COOKIE_ENV = "LIMITORA_AUTH_COOKIE"
_REQUEST = StatusRequest(
    frozenset({MetricKind.COMMERCIAL_QUOTA}),
    AuthorizationPolicy.ALLOW_AUTHORIZED_SOURCE,
    FreshnessPolicy(timedelta(seconds=10)),
)


def _error(provider: ProviderKey, code: SafeErrorCode) -> ProviderView:
    return ProviderView(provider, ProviderState.SAFE_ERROR, SafeError(code))


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
        return ProviderView(provider, ProviderState.UNAVAILABLE)
    if not isinstance(result, StatusSnapshotResult):
        return _error(provider, SafeErrorCode.INTERNAL_ERROR)
    if result.freshness is Freshness.STALE:
        return ProviderView(provider, ProviderState.UNAVAILABLE)
    if result.snapshot.status.state in (LimitoraProviderState.AVAILABLE, LimitoraProviderState.UNAVAILABLE):
        return ProviderView(provider, ProviderState.SUCCESS if result.snapshot.status.state is LimitoraProviderState.AVAILABLE else ProviderState.UNAVAILABLE)
    return _error(provider, SafeErrorCode.PROVIDER_ERROR)


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
        return ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)
    try:
        client = activate_provider(OpenCodeGoConfig(workspace_id, cookie))
    except (CompositionError, TypeError, ValueError):
        return _error(ProviderKey.OPENCODE_GO, SafeErrorCode.CONFIGURATION_INVALID)
    except Exception:  # noqa: BLE001 - construction failures are redacted
        return _error(ProviderKey.OPENCODE_GO, SafeErrorCode.INTERNAL_ERROR)
    return _read(ProviderKey.OPENCODE_GO, client)


__all__ = ("AUTH_COOKIE_ENV", "CodexLimitoraAdapter", "read_codex", "read_opencode_go")
