"""Machine-JSON command-line boundary."""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

from .config import ConfigError, LocalConfig
from .coordinator import RuntimeCoordinator
from .model import DocumentView, ProviderKey, ProviderState, ProviderView, SafeError, SafeErrorCode
from .projection import project_bytes

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


def _load(argv: Sequence[str]) -> LocalConfig:
    path = _config_path(argv)
    if path is None:
        return LocalConfig()
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as error:  # noqa: BLE001 - path and parser details never cross the boundary
        raise ConfigError("invalid local configuration") from error
    return LocalConfig.from_mapping(value)


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
    try:
        config = _load(args)
    except InvocationError:
        document, exit_code, diagnostic = _failure(SafeErrorCode.INVOCATION_INVALID), 2, "invocation_invalid"
    except ConfigError:
        document, exit_code, diagnostic = _failure(SafeErrorCode.CONFIGURATION_INVALID), 2, "configuration_invalid"
    else:
        try:
            active_coordinator = coordinator if coordinator is not None else RuntimeCoordinator()
            document = active_coordinator.run(config, os.environ if environment is None else environment)
        except Exception:  # noqa: BLE001 - the machine boundary must never expose runtime details
            document = _failure(SafeErrorCode.INTERNAL_ERROR)
        exit_code = 1 if any(view.state is ProviderState.SAFE_ERROR for view in document.providers) else 0
        diagnostic = "runtime_error" if exit_code else ""
    _write(out, project_bytes(document))
    if diagnostic:
        err.write(f"yasb-limitora: {diagnostic}\n")
        err.flush()
    return exit_code


__all__ = ("InvocationError", "main")
