"""Build the internal frozen onedir candidate for yasb-limitora (S02).

Runs PyInstaller against packaging/pyinstaller/yasb-limitora.spec with
deterministic-enough inputs (single __version__ source, pinned tool capture,
SOURCE_DATE_EPOCH, rendered version resource) and writes the build record
_internal/build-info.json inside the onedir output. Usage:
python scripts/build_frozen_bundle.py. Output is internal and disposable under
build/frozen/ only; no ZIP or setup artifact is ever published. No network
calls beyond what PyInstaller itself performs locally.
Exit codes: 0 ok; 1 bounded build failure with diagnostics; 2 tooling precondition.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from importlib import metadata
from pathlib import Path

_REQUIRED_PYINSTALLER = ">=6,<7"
_VERSION_RE = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)
_MODULE_RE = re.compile(r"ModuleNotFoundError: No module named '([^']+)'")


class BuildError(RuntimeError):
    """Bounded, sanitized build failure with a machine-readable reason code."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)
        self.reason_code, self.detail = reason_code, detail


def read_product_version(repo_root: Path) -> str:
    source = (repo_root / "src" / "yasb_limitora" / "__init__.py").read_text(encoding="utf-8")
    match = _VERSION_RE.search(source)
    if match is None:
        raise BuildError("version_missing", "no __version__ in package source")
    return match.group(1)


def render_version_info(version: str, template: str) -> str:
    try:
        parts = [int(part) for part in version.split(".")]
    except ValueError:
        parts = []
    if len(parts) != 3:
        raise BuildError("version_invalid", version)
    rendered = template.replace("@@VERSION_TUPLE@@", f"({parts[0]}, {parts[1]}, {parts[2]}, 0)")
    rendered = rendered.replace("@@VERSION@@", version)
    if "@@" in rendered:
        raise BuildError("template_incomplete", "unresolved placeholder")
    return rendered


def check_pyinstaller_version(raw: str | None) -> str:
    if raw is None:
        raise BuildError("pyinstaller_missing", f"PyInstaller {_REQUIRED_PYINSTALLER} not installed")
    if raw.split(".", 1)[0] != "6":
        raise BuildError("pyinstaller_version", f"found {raw}; required {_REQUIRED_PYINSTALLER}")
    return raw


def capture_source_identity(repo_root: Path, env: Mapping[str, str] | None = None,
                             runner: Callable[..., object] = subprocess.run) -> dict[str, str]:
    environment = os.environ if env is None else env

    def git(args: Sequence[str]) -> str:
        done = runner(["git", *args], cwd=repo_root, capture_output=True, text=True, timeout=30)
        if getattr(done, "returncode", 1) != 0:
            raise BuildError("git_unavailable", " ".join(args))
        return str(getattr(done, "stdout", "")).strip()

    commit = git(["rev-parse", "HEAD"])
    epoch = environment.get("SOURCE_DATE_EPOCH", "").strip() or git(["show", "-s", "--format=%ct", "HEAD"])
    if not epoch.isdigit():
        raise BuildError("source_date_epoch_invalid", "SOURCE_DATE_EPOCH must be numeric")
    return {"source_commit": commit, "source_date_epoch": epoch}


def build_info_record(*, version: str, source_commit: str, source_date_epoch: str,
                      python_version: str, pyinstaller_version: str, limitora_version: str) -> dict[str, str]:
    return {"version": version, "source_commit": source_commit, "python": python_version,
            "pyinstaller": pyinstaller_version, "limitora": limitora_version,
            "source_date_epoch": source_date_epoch}


def diagnose_failure(returncode: int, stderr_text: str) -> str:
    bounded = (stderr_text or "").strip()[-1200:]
    match = _MODULE_RE.search(stderr_text or "")
    hint = f"; suspected missing hidden-import '{match.group(1)}': check collect_submodules coverage" if match else ""
    return f"pyinstaller exited {returncode}{hint}\n{bounded}"


def run_build(*, repo_root: Path, output_root: Path, version_info_path: Path,
              runner: Callable[..., object] = subprocess.run, env: Mapping[str, str] | None = None,
              source_date_epoch: str | None = None) -> Path:
    base = dict(os.environ if env is None else env)
    base["YASB_LIMITORA_VERSION_INFO"] = str(version_info_path)
    base["PYTHONHASHSEED"] = "0"
    if source_date_epoch is not None:
        # Propagate the resolved epoch so the PyInstaller child build is timestamp-pinned.
        base["SOURCE_DATE_EPOCH"] = source_date_epoch
    dist_root = output_root / "dist"
    command = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm",
               "--distpath", str(dist_root), "--workpath", str(output_root / "work"),
               str(repo_root / "packaging" / "pyinstaller" / "yasb-limitora.spec")]
    done = runner(command, cwd=repo_root, env=base, capture_output=True, text=True)
    try:
        returncode = int(getattr(done, "returncode", 1))
    except (TypeError, ValueError):
        returncode = 1
    if returncode != 0:
        failed_output = dist_root / "yasb-limitora"
        # Failed output is disposable: remove it, then report bounded diagnostics.
        try:
            shutil.rmtree(failed_output, ignore_errors=True)
        except OSError as cleanup_error:  # pragma: no cover - best-effort cleanup
            print(f"build-frozen-bundle: cleanup_warning: {cleanup_error}", file=sys.stderr)
        raise BuildError("build_failed", diagnose_failure(returncode, str(getattr(done, "stderr", ""))))
    bundle = dist_root / "yasb-limitora"
    if not (bundle / "yasb-limitora.exe").is_file():
        raise BuildError("build_incomplete", "onedir output has no yasb-limitora.exe")
    return bundle


def write_build_info(bundle: Path, record: Mapping[str, str]) -> Path:
    target = bundle / "_internal" / "build-info.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(record), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def _tool_version(distribution: str) -> str | None:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    output_root = repo_root / "build" / "frozen"
    try:
        version = read_product_version(repo_root)
        pyinstaller = check_pyinstaller_version(_tool_version("pyinstaller"))
        limitora = _tool_version("limitora")
        if limitora is None:
            raise BuildError("limitora_missing", "pinned limitora==0.3.1 not installed")
        identity = capture_source_identity(repo_root)
        template = (repo_root / "packaging" / "pyinstaller" / "version_info.txt.in").read_text(encoding="utf-8")
        output_root.mkdir(parents=True, exist_ok=True)
        version_info_path = output_root / "version_info.txt"
        version_info_path.write_text(render_version_info(version, template), encoding="utf-8")
        bundle = run_build(repo_root=repo_root, output_root=output_root, version_info_path=version_info_path,
                           source_date_epoch=identity["source_date_epoch"])
        write_build_info(bundle, build_info_record(
            version=version, source_commit=identity["source_commit"],
            source_date_epoch=identity["source_date_epoch"],
            python_version=".".join(str(part) for part in sys.version_info[:3]),
            pyinstaller_version=pyinstaller, limitora_version=limitora))
    except BuildError as error:
        print(f"build-frozen-bundle: {error.reason_code}: {error.detail}", file=sys.stderr)
        return 2 if error.reason_code.endswith(("missing", "unavailable", "invalid")) else 1
    except OSError as error:
        detail = str(error.strerror) if error.strerror else repr(error)
        print(f"build-frozen-bundle: io_error: {detail}", file=sys.stderr)
        return 2
    print(f"build-frozen-bundle: ok version={version} bundle=build/frozen/dist/yasb-limitora")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
