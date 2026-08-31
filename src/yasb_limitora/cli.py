"""Machine-JSON command-line boundary."""

from __future__ import annotations

import json
import multiprocessing
import ntpath
import os
import re
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any, TextIO, cast

from .codex_helper import (
    _INTERNAL_HELPER_FLAG,
    _has_internal_helper_environment,
    _run_internal_helper,
)
from .config import ConfigError, LocalConfig
from .model import (
    DocumentView,
    ProviderKey,
    ProviderOutcome,
    ProviderState,
    ProviderView,
    SafeError,
    SafeErrorCode,
)
from .projection import (
    ProjectionInput,
    project_bytes,
    project_failure_bytes,
    project_not_run_bytes,
)
from .v2_cache import V2QuotaCache
from .v2_deadline import DeadlineContext
from .v2_path import V2DeadlineError, read_v2_config
from .v2_worker import V2ExecutionOrchestrator

_SECRET = re.compile(r"auth.?cookie|cookie|token|password|secret|credential|api.?key|authorization", re.IGNORECASE)


class InvocationError(ValueError):
    """Raised for unsupported or unsafe command-line arguments."""


def _is_windows_runtime() -> bool:
    return os.name == "nt"


def _config_path(argv: Sequence[str]) -> str | None:
    if not all(isinstance(item, str) for item in argv) or any(_SECRET.search(item) for item in argv):
        raise InvocationError
    if not argv:
        return None
    if len(argv) == 2 and argv[0] in {"--config", "-c"} and argv[1]:
        return argv[1]
    if len(argv) == 1 and argv[0].startswith("--config=") and argv[0][9:]:
        return argv[0][9:]
    raise InvocationError


def _default_windows_config_path(environment: Mapping[str, str]) -> str:
    localappdata = environment.get("LOCALAPPDATA", "")
    if not localappdata or not localappdata.strip():
        raise ConfigError("missing LOCALAPPDATA")
    return ntpath.join(localappdata, "yasb-limitora", "config.json")


def _env_or_default(environment: Mapping[str, str]) -> str:
    if "YASB_LIMITORA_CONFIG" in environment:
        value = environment["YASB_LIMITORA_CONFIG"]
        if not value.strip():
            raise ConfigError("empty YASB_LIMITORA_CONFIG")
        return value
    return _default_windows_config_path(environment)


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError("duplicate configuration key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ConfigError("non-finite configuration number")


def _load_v2_explicit(path: str, context: DeadlineContext | None = None) -> tuple[LocalConfig, frozenset[ProviderKey]]:
    try:
        raw = read_v2_config(path, context or DeadlineContext.from_seconds(1))
        value = json.loads(raw, object_pairs_hook=_unique_json_object, parse_constant=_reject_json_constant)
    except V2DeadlineError as error:
        raise V2DeadlineError("configuration deadline exhausted") from error
    except ConfigError:
        raise
    except Exception as error:
        raise ConfigError("invalid local configuration") from error
    provider_errors: set[ProviderKey] = set()
    return LocalConfig.from_mapping(value, provider_errors=provider_errors), frozenset(provider_errors)


def _load_v2_path(path: str | None, context: DeadlineContext | None = None) -> tuple[LocalConfig, frozenset[ProviderKey]]:
    return (LocalConfig(), frozenset()) if path is None else _load_v2_explicit(path, context)


def _resolve_config_path(argv: Sequence[str], environment: Mapping[str, str]) -> str:
    explicit = _config_path(argv)
    return explicit if explicit is not None else _env_or_default(environment)


def _v2_cache_eligible(config: LocalConfig, environment: Mapping[str, str]) -> bool:
    return bool(
        (config.codex.enabled and config.codex.runner)
        or (
            config.opencode_go.enabled
            and isinstance(environment.get("LIMITORA_OPENCODE_API_KEY"), str)
            and bool(environment["LIMITORA_OPENCODE_API_KEY"])
        )
    )


def _v2_provider_error_overlay(document: DocumentView, provider_errors: frozenset[ProviderKey]) -> DocumentView:
    if not provider_errors:
        return document
    providers = tuple(
        ProviderView(
            view.provider,
            ProviderState.SAFE_ERROR,
            SafeError(SafeErrorCode.PROVIDER_ERROR),
            display_label=view.display_label,
            outcome=ProviderOutcome.EXECUTION_ERROR,
        )
        if view.provider in provider_errors
        else view
        for view in document.providers
    )
    return DocumentView(providers, document.document_error)


def _v2_exit_code(document: DocumentView, enabled: frozenset[ProviderKey]) -> int:
    if document.document_error is not None:
        return 2
    if not any(view.state is ProviderState.SAFE_ERROR for view in document.providers):
        return 0
    usable_outcomes = {ProviderOutcome.SNAPSHOT, ProviderOutcome.UNDETECTED}
    has_usable_provider = any(
        view.outcome in usable_outcomes
        or (
            view.outcome is None
            and view.state is ProviderState.UNAVAILABLE
            and view.provider in enabled
        )
        for view in document.providers
    )
    return 0 if has_usable_provider else 1


def _v2_cache_failure(code: str | None) -> bytes:
    if code in {"guard_wait_timeout", "deadline_exhausted"}:
        return project_not_run_bytes(code)
    if code == "guard_acquisition_failed":
        return project_failure_bytes(code)
    return project_failure_bytes("internal_error")


def _write(stream: object, data: bytes) -> None:
    target = cast(Any, getattr(stream, "buffer", stream))
    try:
        target.write(data)
    except TypeError:
        target.write(data.decode("utf-8"))
    flush = getattr(target, "flush", None)
    if flush is not None:
        flush()


def main(
    argv: Sequence[str] | None = None,
    *,
    environment: Mapping[str, str] | None = None,
    stdout: object | None = None,
    stderr: TextIO | None = None,
    platform_is_windows: Callable[[], bool] = _is_windows_runtime,
) -> int:
    out, err = sys.stdout if stdout is None else stdout, sys.stderr if stderr is None else stderr
    if not platform_is_windows():
        err.write("yasb-limitora: unsupported_platform\n")
        err.flush()
        return 2
    multiprocessing.freeze_support()
    args = tuple(sys.argv[1:] if argv is None else argv)
    if args == (_INTERNAL_HELPER_FLAG,) and _has_internal_helper_environment():
        return _run_internal_helper()
    effective_environment = os.environ if environment is None else environment
    t0_ns = time.monotonic_ns()
    # The current contract is the only runtime path; args remain untouched so
    # removed selectors are rejected by ordinary invocation validation.
    try:
        resolved_v2_path = _resolve_config_path(args, effective_environment)
        config, provider_errors = _load_v2_path(
            resolved_v2_path,
            DeadlineContext.from_seconds(1, t0_ns=t0_ns),
        )
    except InvocationError:
        data, diagnostic = project_failure_bytes("invocation_invalid"), "invocation_invalid"
        _write(out, data)
        err.write(f"yasb-limitora: {diagnostic}\n")
        err.flush()
        return 2
    except V2DeadlineError:
        data, diagnostic = project_failure_bytes("deadline_exhausted"), "runtime_error"
        _write(out, data)
        err.write(f"yasb-limitora: {diagnostic}\n")
        err.flush()
        return 2
    except ConfigError:
        data, diagnostic = project_failure_bytes("configuration_invalid"), "configuration_invalid"
        _write(out, data)
        err.write(f"yasb-limitora: {diagnostic}\n")
        err.flush()
        return 2
    else:
        document: DocumentView | None = None
        opencode_evidence = None
        cached_data = None
        coordination_data = None
        coordination_diagnostic = None
        try:
            orchestrator = V2ExecutionOrchestrator()
            runtime_context = DeadlineContext.from_seconds(config.deadline_seconds, t0_ns=t0_ns)
            result = None
            if not provider_errors and _v2_cache_eligible(config, effective_environment):
                try:
                    cache = V2QuotaCache(config, effective_environment, resolved_v2_path or "")
                except Exception:  # noqa: BLE001 - cache setup is optional infrastructure
                    cache = None
                if cache is not None:
                    try:
                        result = cache.get_or_refresh(
                            runtime_context,
                            lambda attempt_context: orchestrator.run_refresh_attempt(
                                config,
                                effective_environment,
                                attempt_context,
                                resolved_v2_path or "",
                                **({"provider_errors": provider_errors} if provider_errors else {}),
                            ),
                        )
                    except Exception:  # noqa: BLE001 - cache coordination must fail closed
                        result = None
                        coordination_data = _v2_cache_failure(
                            "deadline_exhausted" if runtime_context.usable_ns() <= 0 else "internal_error"
                        )
                    if result is not None:
                        if result.cached_public_bytes is not None:
                            cached_data = result.cached_public_bytes
                        elif result.deadline_exhausted:
                            coordination_data = _v2_cache_failure("deadline_exhausted")
                        elif result.coordination_failed:
                            coordination_data = _v2_cache_failure(result.coordination_error)
                            coordination_diagnostic = (
                                "guard_wait_timeout"
                                if result.coordination_error == "guard_wait_timeout"
                                else "runtime_error"
                            )
                        else:
                            value = result.value
                            if not isinstance(value, DocumentView):
                                raise TypeError("v2 cache did not return a document")
                            document = value
            if cached_data is None and coordination_data is None and result is None:
                document = orchestrator.run(
                    config,
                    effective_environment,
                    runtime_context,
                    resolved_v2_path or "",
                    **({"provider_errors": provider_errors} if provider_errors else {}),
                )
            if orchestrator.last_record is not None:
                opencode_evidence = orchestrator.last_record.opencode_evidence
        except Exception:  # noqa: BLE001 - the machine boundary must never expose runtime details
            data = project_failure_bytes("internal_error")
            _write(out, data)
            err.write("yasb-limitora: runtime_error\n")
            err.flush()
            return 2
        if cached_data is not None:
            data, exit_code, diagnostic = cached_data, 0, ""
        elif coordination_data is not None:
            data, exit_code, diagnostic = coordination_data, 2, coordination_diagnostic or "runtime_error"
        else:
            try:
                if not isinstance(document, DocumentView):
                    raise TypeError("v2 runtime did not return a document")
                enabled = frozenset(
                    provider
                    for provider, enabled_flag in (
                        (ProviderKey.CODEX, config.codex.enabled or ProviderKey.CODEX in provider_errors),
                        (ProviderKey.OPENCODE_GO, config.opencode_go.enabled or ProviderKey.OPENCODE_GO in provider_errors),
                    )
                    if enabled_flag
                )
                document = _v2_provider_error_overlay(document, provider_errors)
                exit_code = _v2_exit_code(document, enabled)
                diagnostic = (
                    "guard_wait_timeout"
                    if document.document_error is not None
                    and document.document_error.code is SafeErrorCode.GUARD_WAIT_TIMEOUT
                    else "runtime_error" if exit_code else ""
                )
                data = project_bytes(ProjectionInput(document, enabled, opencode_evidence))
            except Exception:  # noqa: BLE001 - current projection failures are safe
                data, exit_code, diagnostic = project_failure_bytes("internal_error"), 2, "runtime_error"
    _write(out, data)
    if diagnostic:
        err.write(f"yasb-limitora: {diagnostic}\n")
        err.flush()
    return exit_code


__all__ = ("InvocationError", "main")
