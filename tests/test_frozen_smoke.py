"""S02b frozen-smoke contract tests."""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest  # pyright: ignore[reportMissingImports] - optional test dependency is present at runtime

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "smoke_frozen.py"
_INVALID = '{"execution_state":"execution_error","execution_error":{"code":"invocation_invalid"}}'
_NORMAL = '{"execution_state":"complete","providers":[]}'


@pytest.fixture(scope="module")
def smoke_mod():
    spec = importlib.util.spec_from_file_location("s02b_smoke_frozen", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bundle(tmp_path: Path, version: str = "0.2.0") -> Path:
    bundle = tmp_path / "yasb-limitora"
    (bundle / "_internal").mkdir(parents=True)
    (bundle / "yasb-limitora.exe").write_bytes(b"MZ")
    (bundle / "_internal" / "build-info.json").write_text(
        json.dumps({"version": version}), encoding="utf-8"
    )
    return bundle


def _runner(bundle: Path, argv_log: list[list[str]]):
    def run(cmd, **kwargs):
        argv_log.append([str(part) for part in cmd])
        invalid = "--bogus" in cmd or cmd[-1].endswith("codex-helper")
        code = 2 if invalid else 0
        error = "yasb-limitora: invocation_invalid\n" if code else ""
        output = _INVALID if invalid else _NORMAL
        return type("Result", (), {"returncode": code, "stdout": output, "stderr": error})()

    return run


def _leaking_runner(bundle: Path):
    leak = f"yasb-limitora: invocation_invalid token=hunter2 {bundle}\\yasb-limitora.exe"

    def run(cmd, **kwargs):
        if "--bogus" in cmd:
            return type("R", (), {"returncode": 2, "stdout": _INVALID, "stderr": leak})()
        if cmd[-1].endswith("codex-helper"):
            return type("R", (), {"returncode": 2, "stdout": _INVALID,
                                  "stderr": "yasb-limitora: invocation_invalid\nunexpected diagnostic"})()
        return type("R", (), {"returncode": 0, "stdout": _NORMAL, "stderr": f"warning: {bundle}"})()

    return run


def test_all_checks_pass_and_report_is_sanitized(smoke_mod, tmp_path):
    bundle = _bundle(tmp_path)
    argv_log: list[list[str]] = []
    report = smoke_mod.run_checks(bundle, "0.2.0", runner=_runner(bundle, argv_log))
    assert [check["status"] for check in report] == ["pass"] * 4
    assert {check["name"] for check in report} == {"structure", "invalid-argv", "helper-sentinel", "normal-cli"}
    assert any(argv[-1] == "--__yasb-limitora-codex-helper" for argv in argv_log)
    rendered = smoke_mod.render_report(report, bundle)
    assert "hunter2" not in rendered and str(bundle) not in rendered


def test_leaking_or_unexpected_stderr_fails_closed(smoke_mod, tmp_path):
    bundle = _bundle(tmp_path)
    report = smoke_mod.run_checks(bundle, "0.2.0", runner=_leaking_runner(bundle))
    assert [check["status"] for check in report] == ["pass", "fail", "fail", "fail"]
    assert all("stderr" in check["reason"] for check in report[1:])
    rendered = smoke_mod.render_report(report, bundle)
    assert "hunter2" not in rendered and str(bundle) not in rendered


def test_structure_failures_stop_before_subprocess(smoke_mod, tmp_path):
    bundle = tmp_path / "empty"
    bundle.mkdir()

    def forbidden(*args, **kwargs):
        raise AssertionError("no subprocess after structural failure")

    report = smoke_mod.run_checks(bundle, "0.2.0", runner=forbidden)
    assert len(report) == 1 and report[0]["name"] == "structure"
    assert report[0]["status"] == "fail"


def test_version_mismatch_fails(smoke_mod, tmp_path):
    report = smoke_mod.run_checks(
        _bundle(tmp_path, version="0.1.0"), "0.2.0", runner=_runner(tmp_path, [])
    )
    assert report[0]["status"] == "fail" and "0.2.0" in report[0]["reason"]


def test_cli_failures_are_fail_closed(smoke_mod, tmp_path):
    bundle = _bundle(tmp_path)

    def broken(cmd, **kwargs):
        if "--bogus" in cmd:
            return type("R", (), {"returncode": 0, "stdout": "{}", "stderr": ""})()
        if cmd[-1].endswith("codex-helper"):
            return type("R", (), {"returncode": 2, "stdout": "", "stderr": "Traceback (most recent call last): bootloader"})()
        return type("R", (), {"returncode": 0, "stdout": '{"version":"0.2.0"}', "stderr": ""})()

    report = smoke_mod.run_checks(bundle, "0.2.0", runner=broken)
    assert [check["status"] for check in report] == ["pass", "fail", "fail", "fail"]
    assert "invocation_invalid" in report[1]["reason"]
    assert "helper/bootstrap" in report[2]["reason"]
    assert "removed root version" in report[3]["reason"]


def test_bare_object_rejected_for_missing_error_contract(smoke_mod, tmp_path):
    def bare(cmd, **kwargs):
        return type("R", (), {"returncode": 2, "stdout": "{}", "stderr": "invocation_invalid"})()

    report = smoke_mod.run_checks(_bundle(tmp_path), "0.2.0", runner=bare)
    assert [check["status"] for check in report] == ["pass", "fail", "fail", "fail"]
    assert all("error contract" in check["reason"] for check in report[1:3])
    assert "execution_state" in report[3]["reason"]


def test_timeout_is_bounded_and_sanitized(smoke_mod, tmp_path):
    bundle = _bundle(tmp_path)

    def timeout(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"], stderr=f"token=hunter2 {bundle}")

    report = smoke_mod.run_checks(bundle, "0.2.0", runner=timeout, timeout=1)
    rendered = smoke_mod.render_report(report, bundle)
    assert [check["status"] for check in report[1:]] == ["fail"] * 3
    assert "hunter2" not in rendered and str(bundle) not in rendered and len(rendered) < 1400
