"""C5 semantic verifier and proof-harness documentation contract tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "proof-harness"
VERIFIER = HARNESS / "host" / "verify-c5-silent-uninstall.py"
C5 = HARNESS / "fixtures" / "c5"
SCENARIO = C5 / "scenario.json"
C5_STEPS = C5 / "c5-steps.json"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
SETUP_SOURCE = ROOT / "build" / "c5-rebuild" / "yasb-limitora-0.2.0-setup.exe"
SETUP_SHA256 = "1d58f3618f5b22ddccacc7be2dcf8e3a1e9a90dba57dffe431d8ca8ae6df3394"
FIXTURE_SHA256 = "e16c422f5a2593dd4bfcc1cf5979cfad382769422953ff10202986be8f0a1795"
SCENARIO_SHA256 = "8aca8127167fc5ec0ec143c563e1b14c1d77bf763c8203d2095bd1c515a37c93"
SETUP_NAME = "yasb-limitora-0.2.0-setup.exe"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _capture(phase: str, *, app_present: bool, uninstall_present: bool) -> dict:
    files = [
        {"path": "config.json", "size": 32, "sha256": FIXTURE_SHA256},
        {"path": "quota-v2-cache.json", "size": 32, "sha256": FIXTURE_SHA256},
    ]
    return {
        "schema": "gentle-ai.yasb-limitora.s11b-guest-state/v3",
        "scenario": "silent-uninstall-with-state-root",
        "phase": phase,
        "exactRoots": {"app": "C:\\Users\\runner\\AppData\\Local\\Programs\\yasb-limitora", "state": "C:\\Users\\runner\\AppData\\Local\\yasb-limitora"},
        "uninstallKey": {"path": "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{55D372A6-1DA5-41BE-B7AB-65CAB362E620}_is1", "present": uninstall_present, "values": []},
        "trees": {
            "app": {"present": app_present, "root": "app", "files": [{"path": "yasb-limitora.exe", "size": 1, "sha256": "0" * 64}]} if app_present else {"present": False, "root": "app", "files": []},
            "state": {"present": True, "root": "state", "files": files},
        },
    }


def _valid_evidence(tmp_path: Path) -> tuple[Path, Path]:
    archive = tmp_path / "archive"
    evidence = archive / "evidence"
    input_root = archive / "input"
    evidence.mkdir(parents=True)
    input_root.mkdir(parents=True)
    if not SETUP_SOURCE.is_file():
        pytest.skip("the repository-provided rebuilt C5 setup fixture is unavailable")
    shutil.copyfile(SETUP_SOURCE, input_root / SETUP_NAME)
    shutil.copyfile(SCENARIO, input_root / "scenario.json")
    shutil.copyfile(C5_STEPS, input_root / "c5-steps.json")
    shutil.copytree(C5 / "state-root", input_root / "state-root")
    scenario = json.loads(C5_STEPS.read_text(encoding="utf-8"))
    _write_json(evidence / "silent-uninstall-with-state-root" / "before" / "state-capture.json", _capture("before", app_present=True, uninstall_present=True))
    _write_json(evidence / "silent-uninstall-with-state-root" / "after" / "state-capture.json", _capture("after", app_present=False, uninstall_present=False))
    run_root = evidence / "silent-uninstall-with-state-root"
    setup_record = {
        "schema": "gentle-ai.yasb-limitora.c5-run/v1",
        "kind": "install",
        "phase": "install",
        "executable": {"path": r"C:\\inputs\\yasb-limitora-0.2.0-setup.exe", "present": True, "name": SETUP_NAME, "size": 11054574, "sha256": SETUP_SHA256},
        "arguments": ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
        "exitCode": 0,
        "dialogAnswerAttempted": False,
    }
    uninstall_record = {
        "schema": "gentle-ai.yasb-limitora.c5-run/v1",
        "kind": "uninstall",
        "phase": "uninstall",
        "executable": {"path": r"C:\\Users\\runner\\AppData\\Local\\Programs\\yasb-limitora\\unins000.exe", "present": True, "name": "unins000.exe", "size": 1, "sha256": "2" * 64},
        "arguments": ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
        "exitCode": 0,
        "dialogAnswerAttempted": False,
    }
    _write_json(run_root / "install" / "run-record.json", setup_record)
    _write_json(run_root / "uninstall" / "run-record.json", uninstall_record)
    result = {
        "schema": "gentle-ai.yasb-limitora.c5-result/v1",
        "scenario": scenario["scenario"],
        "legacyScenarioSha256": SCENARIO_SHA256,
        "setup": {"name": SETUP_NAME, "size": 11054574, "sha256": SETUP_SHA256},
        "silentArguments": ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
        "fixtureFiles": [{"path": "config.json", "size": 32, "sha256": FIXTURE_SHA256}, {"path": "quota-v2-cache.json", "size": 32, "sha256": FIXTURE_SHA256}],
        "statePreserved": True,
        "applicationRemoved": True,
        "uninstallKeyRemoved": True,
        "dialogAnswerAttempted": False,
    }
    _write_json(evidence / "c5-result.json", result)
    _write_json(evidence / "done.json", {"schema": "gentle-ai.yasb-limitora.reusable-vm-done/v1", "scenario": scenario["scenario"], "result": "success", "runnerExitCode": 0, "inputTreeSha256": "a" * 64, "inputUnchanged": True, "shutdownRequested": True})
    _write_json(evidence / "exit.json", {"schema": "gentle-ai.yasb-limitora.reusable-vm-exit/v1", "scenario": scenario["scenario"], "success": True, "exitCode": 0, "runnerExitCode": 0, "failure": None, "shutdownRequested": True})
    return archive, evidence


def _run_verifier(archive: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(VERIFIER), str(archive)], text=True, capture_output=True, check=False)


def test_c5_offline_verifier_accepts_complete_evidence(tmp_path: Path) -> None:
    archive, evidence = _valid_evidence(tmp_path)
    result = _run_verifier(archive)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "C5 VERDICT: PASS" in result.stdout


@pytest.mark.parametrize(
    ("mutation", "needle"),
    [
        ("setup_hash", "setup"),
        ("state_hash", "state"),
        ("missing_state", "capture"),
        ("app_remains", "application"),
        ("uninstall_remains", "uninstall"),
        ("missing_capture", "capture"),
        ("missing_run", "run record"),
        ("missing_identity", "identity"),
        ("bad_exit", "exit"),
        ("boolean_exit", "exit"),
        ("boolean_success", "success"),
        ("dialog_answers", "dialog"),
        ("scenario_bytes", "scenario sha-256"),
        ("fixture_bytes", "fixture"),
        ("dialog_answer_omitted", "dialog"),
        ("dialog", "dialog"),
    ],
)
def test_c5_offline_verifier_rejects_each_contract_break(tmp_path: Path, mutation: str, needle: str) -> None:
    archive, evidence = _valid_evidence(tmp_path)
    if mutation == "setup_hash":
        payload = json.loads((evidence / "c5-result.json").read_text(encoding="utf-8"))
        payload["setup"]["sha256"] = "0" * 64
        _write_json(evidence / "c5-result.json", payload)
    elif mutation == "state_hash":
        path = evidence / "silent-uninstall-with-state-root" / "after" / "state-capture.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["trees"]["state"]["files"][0]["sha256"] = "0" * 64
        _write_json(path, payload)
    elif mutation == "missing_state":
        (evidence / "silent-uninstall-with-state-root" / "after" / "state-capture.json").unlink()
    elif mutation == "app_remains":
        path = evidence / "silent-uninstall-with-state-root" / "after" / "state-capture.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["trees"]["app"]["present"] = True
        _write_json(path, payload)
    elif mutation == "uninstall_remains":
        path = evidence / "silent-uninstall-with-state-root" / "after" / "state-capture.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["uninstallKey"]["present"] = True
        _write_json(path, payload)
    elif mutation == "missing_capture":
        (evidence / "silent-uninstall-with-state-root" / "before" / "state-capture.json").unlink()
    elif mutation == "missing_run":
        (evidence / "silent-uninstall-with-state-root" / "install" / "run-record.json").unlink()
    elif mutation == "missing_identity":
        path = evidence / "silent-uninstall-with-state-root" / "uninstall" / "run-record.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        del payload["executable"]["present"]
        _write_json(path, payload)
    elif mutation == "bad_exit":
        path = evidence / "silent-uninstall-with-state-root" / "uninstall" / "run-record.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["exitCode"] = 23
        _write_json(path, payload)
    elif mutation == "boolean_exit":
        path = evidence / "exit.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["exitCode"] = False
        _write_json(path, payload)
    elif mutation == "boolean_success":
        path = evidence / "exit.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["success"] = "true"
        _write_json(path, payload)
    elif mutation == "dialog_answers":
        path = archive / "input" / "scenario.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["dialogAnswers"] = [{"match": "unexpected"}]
        _write_json(path, payload)
    elif mutation == "scenario_bytes":
        path = archive / "input" / "scenario.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["tampered"] = True
        _write_json(path, payload)
    elif mutation == "fixture_bytes":
        (archive / "input" / "state-root" / "config.json").write_bytes(b"x" * 32)
    elif mutation == "dialog_answer_omitted":
        path = evidence / "silent-uninstall-with-state-root" / "install" / "run-record.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        del payload["dialogAnswerAttempted"]
        _write_json(path, payload)
    elif mutation == "dialog":
        path = evidence / "silent-uninstall-with-state-root" / "uninstall" / "run-record.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["dialogObserved"] = True
        _write_json(path, payload)
    result = _run_verifier(archive)
    assert result.returncode != 0
    assert needle in result.stdout.lower()


def test_readme_uses_command_array_binding_and_actual_archive_layout() -> None:
    readme = (HARNESS / "README.md").read_text(encoding="utf-8")
    assert "pwsh -NoProfile -Command" in readme
    assert "-AdditionalInputPath @(" in readme
    assert "<EvidenceRoot>\\runs\\run-<id>" in readme
    assert "-File proof-harness/host/run-reusable-vm.ps1" not in readme
