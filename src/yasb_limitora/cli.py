"""Machine-JSON command-line boundary."""

from __future__ import annotations

import json
import ntpath
import os
import re
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

from .config import ConfigError, LocalConfig
from .coordinator import RuntimeCoordinator
from .model import DocumentView, ProviderKey, ProviderState, ProviderView, SafeError, SafeErrorCode, V2SafeErrorCode
from .projection import project_bytes
from .projection_v2 import V2ProjectionInput, project_v2_bytes, project_v2_failure_bytes
from .v2_deadline import DeadlineContext
from .v2_path import V2DeadlineError, read_v2_config
from .v2_worker import V2ExecutionOrchestrator

_SECRET = re.compile(r"auth.?cookie|cookie|token|password|secret|credential|api.?key|authorization", re.I)


class InvocationError(ValueError):
    """Raised for unsupported or unsafe command-line arguments."""


def _failure(code: SafeErrorCode) -> DocumentView:
    error = SafeError(code)
    return DocumentView.ordered(
        ProviderView(ProviderKey.CODEX, ProviderState.SAFE_ERROR, error),
        ProviderView(ProviderKey.OPENCODE_GO, ProviderState.SAFE_ERROR, error),
    )


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


def _output_version(argv: Sequence[str]) -> tuple[int | None, tuple[str, ...]]:
    """Remove one exact output selector, leaving the frozen v1 arguments intact."""

    if not all(isinstance(item, str) for item in argv):
        raise InvocationError
    version: int | None = None
    remaining: list[str] = []
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument == "--output-version":
            if version is not None or index + 1 >= len(argv):
                raise InvocationError
            value = argv[index + 1]
            if value not in {"1", "2"}:
                raise InvocationError
            version = int(value)
            index += 2
            continue
        if argument.startswith("--output-version="):
            if version is not None or argument[17:] not in {"1", "2"}:
                raise InvocationError
            version = int(argument[17:])
            index += 1
            continue
        remaining.append(argument)
        index += 1
    return version, tuple(remaining)


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


def _read_config(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


_LEGACY_READ_CONFIG = _read_config


def _load_explicit(path: str) -> LocalConfig:
    try:
        value = json.loads(_read_config(path))
    except Exception as error:  # noqa: BLE001 - path and parser details never cross the boundary
        raise ConfigError("invalid local configuration") from error
    return LocalConfig.from_mapping(value)


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError("duplicate configuration key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ConfigError("non-finite configuration number")


def _load_v2_explicit(path: str, context: DeadlineContext | None = None) -> LocalConfig:
    try:
        if _read_config is not _LEGACY_READ_CONFIG:
            raw = _read_config(path)
        else:
            raw = read_v2_config(path, context or DeadlineContext.from_seconds(1))
        value = json.loads(raw, object_pairs_hook=_unique_json_object, parse_constant=_reject_json_constant)
    except V2DeadlineError as error:
        raise V2DeadlineError("configuration deadline exhausted") from error
    except ConfigError:
        raise
    except Exception as error:  # noqa: BLE001 - path and parser details never cross the boundary
        raise ConfigError("invalid local configuration") from error
    return LocalConfig.from_v2_mapping(value)


def _load_path(path: str | None) -> LocalConfig:
    return LocalConfig() if path is None else _load_explicit(path)


def _load_v2_path(path: str | None, context: DeadlineContext | None = None) -> LocalConfig:
    return LocalConfig() if path is None else _load_v2_explicit(path, context)


def _resolve_config_path(argv: Sequence[str], environment: Mapping[str, str]) -> str:
    explicit = _config_path(argv)
    return explicit if explicit is not None else _env_or_default(environment)


def _load(argv: Sequence[str]) -> LocalConfig:
    return _load_path(_config_path(argv))


def _write(stream: object, data: bytes) -> None:
    target = getattr(stream, "buffer", stream)
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
    coordinator: RuntimeCoordinator | None = None,
    stdout: object | None = None,
    stderr: TextIO | None = None,
) -> int:
    args = tuple(sys.argv[1:] if argv is None else argv)
    out, err = sys.stdout if stdout is None else stdout, sys.stderr if stderr is None else stderr
    effective_environment = os.environ if environment is None else environment
    t0_ns = time.monotonic_ns()
    try:
        version, load_args = _output_version(args)
    except InvocationError:
        _write(out, project_bytes(_failure(SafeErrorCode.INVOCATION_INVALID)))
        err.write("yasb-limitora: invocation_invalid\n")
        err.flush()
        return 2
    try:
        resolved_v2_path = None
        config = (
            _load_v2_path(
                (resolved_v2_path := _resolve_config_path(load_args, effective_environment)),
                DeadlineContext.from_seconds(1, t0_ns=t0_ns),
            )
            if version == 2
            else _load(load_args)
        )
    except InvocationError:
        if version == 2:
            data, diagnostic = project_v2_failure_bytes("invocation_invalid"), "invocation_invalid"
        else:
            data, diagnostic = project_bytes(_failure(SafeErrorCode.INVOCATION_INVALID)), "invocation_invalid"
        _write(out, data)
        err.write(f"yasb-limitora: {diagnostic}\n")
        err.flush()
        return 2
    except V2DeadlineError:
        if version == 2:
            data, diagnostic = project_v2_failure_bytes("deadline_exhausted"), "runtime_error"
            _write(out, data)
            err.write(f"yasb-limitora: {diagnostic}\n")
            err.flush()
            return 1
        raise
    except ConfigError:
        if version == 2:
            data, diagnostic = project_v2_failure_bytes("configuration_invalid"), "configuration_invalid"
        else:
            data, diagnostic = project_bytes(_failure(SafeErrorCode.CONFIGURATION_INVALID)), "configuration_invalid"
        _write(out, data)
        err.write(f"yasb-limitora: {diagnostic}\n")
        err.flush()
        return 2
    else:
        try:
            if version == 2 and coordinator is None and _read_config is _LEGACY_READ_CONFIG:
                document = V2ExecutionOrchestrator().run(
                    config,
                    effective_environment,
                    DeadlineContext.from_seconds(config.deadline_seconds, t0_ns=t0_ns),
                    resolved_v2_path or "",
                )
            else:
                active_coordinator = coordinator if coordinator is not None else RuntimeCoordinator()
                document = active_coordinator.run(config, effective_environment)
        except Exception:  # noqa: BLE001 - the machine boundary must never expose runtime details
            if version == 2:
                data = project_v2_failure_bytes("internal_error")
            else:
                data = project_bytes(_failure(SafeErrorCode.INTERNAL_ERROR))
            _write(out, data)
            err.write("yasb-limitora: runtime_error\n")
            err.flush()
            return 1
        if version == 2:
            try:
                exit_code = 1 if document.document_error is not None or any(view.state is ProviderState.SAFE_ERROR for view in document.providers) else 0
                diagnostic = (
                    "guard_wait_timeout"
                    if document.document_error is not None and document.document_error.code is V2SafeErrorCode.GUARD_WAIT_TIMEOUT
                    else "runtime_error" if exit_code else ""
                )
                enabled = frozenset(
                    provider
                    for provider, enabled_flag in (
                        (ProviderKey.CODEX, config.codex.enabled),
                        (ProviderKey.OPENCODE_GO, config.opencode_go.enabled),
                    )
                    if enabled_flag
                )
                data = project_v2_bytes(V2ProjectionInput(document, enabled))
            except Exception:  # noqa: BLE001 - v2 projection failures are safe
                data, exit_code, diagnostic = project_v2_failure_bytes("internal_error"), 1, "runtime_error"
        else:
            exit_code = 1 if any(view.state is ProviderState.SAFE_ERROR for view in document.providers) else 0
            diagnostic = "runtime_error" if exit_code else ""
            data = project_bytes(document)
    _write(out, data)
    if diagnostic:
        err.write(f"yasb-limitora: {diagnostic}\n")
        err.flush()
    return exit_code


__all__ = ("InvocationError", "main")
