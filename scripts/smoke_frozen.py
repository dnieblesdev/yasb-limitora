"""Bounded smoke driver for the internal frozen onedir candidate (S02): build-info,
normal CLI JSON contract (recognized root execution_state, no removed root version),
invalid-argv, and helper/bootstrap sentinel checks; sanitized bounded reports; no
network; one disposable temp config removed on exit. Strict stderr: passing streams must
be empty and invalid streams must carry only the exact invocation_invalid diagnostic.
Exit codes: 0 passed; 1 failed;
2 usage. Usage: python scripts/smoke_frozen.py <onedir-bundle-root> [--expect-version X.Y.Z]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

_EXE_NAME = "yasb-limitora.exe"
_HELPER_SENTINEL = "--__yasb-limitora-codex-helper"
_TIMEOUT_SECONDS = 60
_MAX_EXCERPT = 240
_HELPER_ENV_KEYS = ("_YASB_CODEX_GATE_HANDLE", "_YASB_CODEX_DATA_HANDLE", "_YASB_CODEX_READY_NONCE")
_SECRET = re.compile(r"(?i)\S*(token|password|secret|cookie|credential|api.?key|authorization)\S*")
_STATES = {"complete", "partial", "not_run", "execution_error"}
_DIAGNOSTIC = "yasb-limitora: invocation_invalid"


def _sanitize(text: str, bundle_root: Path) -> str:
    cleaned = _SECRET.sub("<redacted>", (text or "").strip()).replace(str(bundle_root), "<bundle>")
    return cleaned[-_MAX_EXCERPT:] if len(cleaned) > _MAX_EXCERPT else cleaned


def _child_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key not in _HELPER_ENV_KEYS}


def _json_defect(bundle_root: Path, stdout: str, expect_error: bool) -> str:
    try:
        document = json.loads(stdout)
    except ValueError:
        return "stdout is not JSON: " + _sanitize(stdout, bundle_root)
    if type(document) is not dict:
        return "stdout JSON is not an object"
    if "version" in document:
        return "stdout carries a removed root version field"
    state, error = document.get("execution_state"), document.get("execution_error")
    if expect_error:
        contract = state == "execution_error" and type(error) is dict and error.get("code") == "invocation_invalid"
        return "" if contract else "stdout lacks the invocation_invalid error contract"
    return "" if state in _STATES else "stdout has no recognized root execution_state"


def _stderr_defect(name: str, err: str, bundle_root: Path) -> str:
    lines = [line.strip() for line in (err or "").splitlines() if line.strip()]
    if name == "normal-cli":
        return "" if not lines else f"passing stream leaked stderr: {_sanitize(err, bundle_root)}"
    unexpected = [line for line in lines if line != _DIAGNOSTIC]
    return "" if not unexpected else f"stderr carries unexpected content: {_sanitize(' | '.join(unexpected), bundle_root)}"


def check_structure(bundle_root: Path, expected_version: str | None) -> dict[str, str]:
    info_path = bundle_root / "_internal" / "build-info.json"
    if not (bundle_root / _EXE_NAME).is_file():
        return {"name": "structure", "status": "fail", "reason": f"{_EXE_NAME} is missing"}
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"name": "structure", "status": "fail", "reason": "_internal/build-info.json missing or invalid"}
    version = info.get("version") if type(info) is dict else None
    if not isinstance(version, str) or not version:
        return {"name": "structure", "status": "fail", "reason": "build-info.json has no version"}
    if expected_version is not None and version != expected_version:
        return {"name": "structure", "status": "fail", "reason": f"build-info version {version} != expected {expected_version}"}
    return {"name": "structure", "status": "pass", "reason": f"version {version}"}


def _validate(name: str, code: int, out: str, err: str, bundle_root: Path) -> str:
    if name == "normal-cli":
        defect = _json_defect(bundle_root, out, expect_error=False) or _stderr_defect(name, err, bundle_root)
        return defect or ("" if code in (0, 1) else f"expected bounded exit 0/1; got {code}: {_sanitize(err, bundle_root)}")
    defect = _json_defect(bundle_root, out, expect_error=True) or _stderr_defect(name, err, bundle_root)
    ok = code == 2 and "invocation_invalid" in err and not defect
    if name == "helper-sentinel":
        ok = ok and "traceback" not in err.lower() and "bootloader" not in err.lower()
    if ok:
        return ""
    label = ("helper/bootstrap path misbehaved without helper env" if name == "helper-sentinel"
             else "expected exit 2 with invocation_invalid")
    detail = defect or f"got exit {code}: {_sanitize(err, bundle_root)}"
    return f"{label}; {detail}"


def run_checks(bundle_root: Path, expected_version: str | None,
               runner: Callable[..., object] = subprocess.run,
               timeout: int = _TIMEOUT_SECONDS) -> list[dict[str, str]]:
    structure = check_structure(bundle_root, expected_version)
    if structure["status"] != "pass":
        return [structure]
    exe = str(bundle_root / _EXE_NAME)
    checks = [structure]
    with tempfile.TemporaryDirectory(prefix="yasb-limitora-smoke-") as holder:
        config_path = Path(holder) / "config.json"
        config_path.write_text("{}", encoding="utf-8")
        for name, argv in (("invalid-argv", ["--bogus"]), ("helper-sentinel", [_HELPER_SENTINEL]),
                           ("normal-cli", ["--config", str(config_path)])):
            try:
                done = runner([exe, *argv], capture_output=True, text=True, timeout=timeout, env=_child_env())
            except Exception as error:  # noqa: BLE001 - bounded sanitized smoke reporting
                checks.append({"name": name, "status": "fail", "reason": _sanitize(repr(error), bundle_root)})
                continue
            try:
                code = int(getattr(done, "returncode", 1))
            except (TypeError, ValueError):
                code = 1
            defect = _validate(name, code, str(getattr(done, "stdout", "")),
                               str(getattr(done, "stderr", "")), bundle_root)
            checks.append({"name": name, "status": "fail" if defect else "pass", "reason": defect})
    return checks


def render_report(checks: Sequence[dict[str, str]], bundle_root: Path) -> str:
    return json.dumps({"bundle": "<bundle>", "checks": list(checks)})


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    expected = None
    if "--expect-version" in args:
        index = args.index("--expect-version")
        if index + 1 >= len(args):
            print("smoke-frozen: --expect-version needs a value", file=sys.stderr)
            return 2
        expected = args[index + 1]
        del args[index:index + 2]
    if len(args) != 1:
        print("smoke-frozen: usage: smoke_frozen.py <bundle-root> [--expect-version X]", file=sys.stderr)
        return 2
    bundle_root = Path(args[0])
    checks = run_checks(bundle_root, expected)
    print(render_report(checks, bundle_root))
    return 0 if all(check["status"] == "pass" for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
