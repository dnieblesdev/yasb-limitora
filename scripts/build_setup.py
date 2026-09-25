"""Build the yasb-limitora Inno Setup installer from a frozen bundle.

Usage:
  python scripts/build_setup.py --source-dir PATH --output-dir PATH \
      --app-version VERSION [--iscc ISCC.exe] [--timeout SECONDS]

The source directory must contain the frozen executable and build information.
This driver only invokes the repository's Inno Setup script; it does not
publish, repack, or create release metadata. Exit code 0 means success, 1
means ISCC failed or timed out, and 2 means an input or tooling precondition
failed.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

_DEFAULT_TIMEOUT = 300.0
_DIAGNOSTIC_LIMIT = 4000
_MAX_BUILD_INFO_BYTES = 64 * 1024
_INNO_SCRIPT = Path("packaging") / "inno" / "yasb-limitora.iss"


class BuildError(RuntimeError):
    """A bounded setup-build failure with a stable reason code."""

    def __init__(self, reason_code: str, detail: str = "", exit_code: int = 1) -> None:
        message = f"{reason_code}: {detail}" if detail else reason_code
        super().__init__(message)
        self.reason_code = reason_code
        self.detail = detail
        self.exit_code = exit_code


def _positive_timeout(value: str) -> float:
    """Parse a finite, strictly positive timeout for argparse."""
    try:
        timeout = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("timeout must be a number") from error
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("timeout must be a finite number greater than zero")
    return timeout


def _as_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value or "")


def _bound(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    marker = "...[truncated]...\n"
    if limit <= len(marker):
        return text[-limit:]
    return marker + text[-(limit - len(marker)) :]


def bounded_diagnostics(stdout: object = "", stderr: object = "", limit: int = _DIAGNOSTIC_LIMIT) -> str:
    """Return both streams with a strict bound per stream and in total."""
    if limit <= 0:
        return ""
    stream_limit = max(1, limit // 2)
    parts = []
    for name, value in (("stdout", stdout), ("stderr", stderr)):
        text = _as_text(value).strip()
        if text:
            parts.append(f"{name}:\n{_bound(text, stream_limit)}")
    return _bound("\n".join(parts), limit)


def _regular_file(path: Path) -> bool:
    """Require an ordinary file rather than a directory or symlink."""
    return path.is_file() and not path.is_symlink()


def validate_source_dir(source_dir: Path) -> Path:
    """Validate and return the caller-resolved frozen bundle directory."""
    source_dir = source_dir.expanduser().resolve()
    if not source_dir.is_dir():
        raise BuildError("source_dir_invalid", f"not a directory: {source_dir}", 2)

    executable = source_dir / "yasb-limitora.exe"
    build_info = source_dir / "_internal" / "build-info.json"
    if not _regular_file(executable):
        raise BuildError("source_executable_missing", f"regular file required: {executable}", 2)
    if not _regular_file(build_info):
        raise BuildError("build_info_missing", f"regular file required: {build_info}", 2)
    return source_dir


def validate_build_info(source_dir: Path, app_version: str) -> None:
    """Validate bounded frozen metadata and bind it to the requested version."""
    build_info = source_dir / "_internal" / "build-info.json"
    try:
        with build_info.open("rb") as stream:
            raw = stream.read(_MAX_BUILD_INFO_BYTES + 1)
    except OSError as error:
        raise BuildError("build_info_invalid", "build information could not be read", 2) from error
    if len(raw) > _MAX_BUILD_INFO_BYTES:
        raise BuildError("build_info_invalid", "build information exceeds the size limit", 2)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BuildError("build_info_invalid", "build information is not valid UTF-8 JSON", 2) from error
    if not isinstance(payload, dict):
        raise BuildError("build_info_invalid", "build information root must be an object", 2)
    version = payload.get("version")
    if not isinstance(version, str) or not version or version != version.strip():
        raise BuildError("build_info_invalid", "build information version is invalid", 2)
    if version != app_version:
        raise BuildError("build_info_version_mismatch", "build information version does not match app version", 2)


def run_setup(
    *,
    source_dir: Path,
    output_dir: Path,
    app_version: str,
    iscc: str = "ISCC.exe",
    timeout: float = _DEFAULT_TIMEOUT,
    repo_root: Path | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> None:
    """Validate inputs and invoke ISCC once with explicit preprocessor defines."""
    source_dir = validate_source_dir(source_dir)
    if not app_version.strip():
        raise BuildError("app_version_invalid", "app version must not be empty", 2)
    if not iscc.strip():
        raise BuildError("iscc_invalid", "ISCC executable must not be empty", 2)
    if not math.isfinite(timeout) or timeout <= 0:
        raise BuildError("timeout_invalid", "timeout must be finite and greater than zero", 2)

    root = (Path(__file__).resolve().parents[1] if repo_root is None else repo_root).resolve()
    inno_script = root / _INNO_SCRIPT
    if not inno_script.is_file():
        raise BuildError("inno_script_missing", f"repository script not found: {inno_script}", 2)

    output_dir = output_dir.expanduser().resolve()
    validate_build_info(source_dir, app_version)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise BuildError("output_dir_unavailable", str(error), 2) from error

    command = [
        iscc,
        f"/DAppVersion={app_version}",
        f"/DSourceDir={source_dir}",
        f"/DOutputDir={output_dir}",
        str(inno_script),
    ]
    try:
        completed = runner(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as error:
        raise BuildError("iscc_missing", f"executable not found: {iscc}", 2) from error
    except subprocess.TimeoutExpired as error:
        diagnostics = bounded_diagnostics(
            getattr(error, "stdout", getattr(error, "output", "")),
            getattr(error, "stderr", ""),
        )
        raise BuildError("iscc_timeout", diagnostics, 1) from error
    except OSError as error:
        raise BuildError("iscc_unavailable", str(error), 2) from error

    try:
        returncode = int(getattr(completed, "returncode", 1))
    except (TypeError, ValueError):
        returncode = 1
    if returncode != 0:
        diagnostics = bounded_diagnostics(
            getattr(completed, "stdout", ""),
            getattr(completed, "stderr", ""),
        )
        detail = f"returncode={returncode}"
        if diagnostics:
            detail += f"\n{diagnostics}"
        raise BuildError("iscc_failed", detail, 1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True, help="frozen onedir bundle")
    parser.add_argument("--output-dir", type=Path, required=True, help="installer output directory")
    parser.add_argument("--app-version", required=True, help="version passed to Inno Setup")
    parser.add_argument("--iscc", default="ISCC.exe", help="ISCC executable (default: ISCC.exe)")
    parser.add_argument(
        "--timeout",
        type=_positive_timeout,
        default=_DEFAULT_TIMEOUT,
        metavar="SECONDS",
        help=f"maximum ISCC runtime (default: {_DEFAULT_TIMEOUT:g})",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run_setup(
            source_dir=args.source_dir,
            output_dir=args.output_dir,
            app_version=args.app_version,
            iscc=args.iscc,
            timeout=args.timeout,
        )
    except BuildError as error:
        detail = f"\n{error.detail}" if error.detail else ""
        print(f"build-setup: {error.reason_code}:{detail}", file=sys.stderr)
        return error.exit_code
    print(f"build-setup: ok version={args.app_version} output={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
