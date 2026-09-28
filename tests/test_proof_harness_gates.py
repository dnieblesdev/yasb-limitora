"""T2 regression tests for fail-closed proof-harness gates."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "proof-harness" / "host" / "verify-evidence.py"
WATCHER = ROOT / "proof-harness" / "guest" / "watch-scenarios.ps1"
ROUNDTRIP = ROOT / "proof-harness" / "host" / "roundtrip-verify.ps1"
POWERSHELL = shutil.which("powershell.exe")
EXPECTED_EXE = "a" * 64
WATCHER_SHA = "b" * 64


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path, *, dialog: bool = False, assist: bool = False) -> Path:
    root = tmp_path / "evidence"
    scenario: dict[str, object] = {
        "schema": "gentle-ai.yasb-limitora.s11b-scenario/v1",
        "scenario": "smoke",
        "steps": [
            {"kind": "capture", "phase": "before"},
            {
                "kind": "setup",
                "phase": "install",
                "executable": "candidate.exe",
                "expectFailure": False,
            },
        ],
        "dialogAnswers": (
            [{"match": "Continue?", "answer": "YES"}] if dialog else []
        ),
        "shutdownWhenDone": True,
    }
    if assist:
        scenario["assist"] = {"marker": "assist completed"}
    _write_json(root / "scenario.json", scenario)
    (root / "expected-watcher.sha256").write_text(WATCHER_SHA + "\n", encoding="utf-8")
    log = f"watcher script sha256={WATCHER_SHA}\n"
    if dialog:
        log += "answering declared dialog (button=6) for setup/install\n"
    if assist:
        log += "assist completed\n"
    (root / "watcher.log").write_text(log, encoding="utf-8")
    _write_json(
        root / "done.json",
        {
            "schema": "gentle-ai.yasb-limitora.s11b-done/v1",
            "scenario": "smoke",
            "result": "success",
            "shutdownSkipped": False,
            "steps": [
                {"kind": "capture", "phase": "before", "exitCode": 0},
                {
                    "kind": "setup",
                    "phase": "install",
                    "executable": "candidate.exe",
                    "exitCode": 0,
                    "dialogAnswered": dialog,
                },
            ],
        },
    )
    _write_json(
        root / "smoke" / "before" / "state-capture.json",
        {
            "schema": "gentle-ai.yasb-limitora.s11b-guest-state/v3",
            "scenario": "smoke",
            "phase": "before",
            "trees": {
                "app": {"present": True, "files": [{"path": "app.exe", "size": 1}]},
                "state": {"present": True, "files": []},
            },
        },
    )
    _write_json(
        root / "smoke" / "install" / "run-1" / "run-record.json",
        {
            "schema": "gentle-ai.yasb-limitora.s11b-guest-run/v2",
            "kind": "setup",
            "scenario": "smoke",
            "phase": "install",
            "executable": {
                "path": r"D:\setups\candidate.exe",
                "size": 10,
                "sha256": EXPECTED_EXE,
            },
            "exitCode": 0,
        },
    )
    return root


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERIFY), str(root), "--expected-executable", EXPECTED_EXE],
        text=True,
        capture_output=True,
        check=False,
    )


def test_complete_evidence_passes_without_unsupported_claims(tmp_path: Path) -> None:
    result = _run(_fixture(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "scenarios=1" in result.stdout
    assert "run_records=1" in result.stdout
    assert "VERDICT: PASS" in result.stdout


def test_missing_or_mismatched_watcher_stamp_fails_closed(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    (root / "expected-watcher.sha256").unlink()
    result = _run(root)
    assert result.returncode != 0
    assert "watcher" in result.stdout.lower()

    root = _fixture(tmp_path / "mismatch")
    (root / "expected-watcher.sha256").write_text("c" * 64 + "\n", encoding="utf-8")
    result = _run(root)
    assert result.returncode != 0
    assert "watcher" in result.stdout.lower()


def test_declared_expected_failure_is_allowed_when_recorded(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    scenario = json.loads((root / "scenario.json").read_text(encoding="utf-8"))
    scenario["steps"][1]["expectFailure"] = True
    _write_json(root / "scenario.json", scenario)
    done = json.loads((root / "done.json").read_text(encoding="utf-8"))
    done["steps"][1]["exitCode"] = 23
    _write_json(root / "done.json", done)
    record = root / "smoke" / "install" / "run-1" / "run-record.json"
    payload = json.loads(record.read_text(encoding="utf-8"))
    payload["exitCode"] = 23
    _write_json(record, payload)
    result = _run(root)
    assert result.returncode == 0, result.stdout + result.stderr


def test_declared_capture_and_input_identity_are_covered(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    (root / "smoke" / "before" / "state-capture.json").unlink()
    result = _run(root)
    assert result.returncode != 0
    assert "state capture" in result.stdout.lower()

    root = _fixture(tmp_path / "identity")
    record = root / "smoke" / "install" / "run-1" / "run-record.json"
    payload = json.loads(record.read_text(encoding="utf-8"))
    payload["executable"]["sha256"] = "c" * 64
    _write_json(record, payload)
    result = _run(root)
    assert result.returncode != 0
    assert "expected" in result.stdout.lower() or "identity" in result.stdout.lower()


def test_declared_dialog_and_assist_claims_need_meaningful_evidence(tmp_path: Path) -> None:
    root = _fixture(tmp_path, dialog=True, assist=True)
    assert _run(root).returncode == 0

    root = _fixture(tmp_path / "dialog-missing")
    scenario = json.loads((root / "scenario.json").read_text(encoding="utf-8"))
    scenario["dialogAnswers"] = [{"match": "Continue?", "answer": "YES"}]
    _write_json(root / "scenario.json", scenario)
    result = _run(root)
    assert result.returncode != 0
    assert "dialog" in result.stdout.lower()

    root = _fixture(tmp_path / "assist-missing")
    scenario = json.loads((root / "scenario.json").read_text(encoding="utf-8"))
    scenario["assist"] = {"marker": "assist completed"}
    _write_json(root / "scenario.json", scenario)
    result = _run(root)
    assert result.returncode != 0
    assert "assist" in result.stdout.lower()


def test_ordered_dictionary_exit_code_gate_is_fail_closed() -> None:
    text = WATCHER.read_text(encoding="utf-8")
    assert "System.Collections.IDictionary" in text
    assert "expectFailure" in text


def _run_dismount_probe(mock: str) -> subprocess.CompletedProcess[str]:
    assert POWERSHELL is not None
    text = ROUNDTRIP.read_text(encoding="utf-8")
    start = text.index("function Assert-IsoDismounted")
    end = text.index("\n}\n\nAssert-File", start) + 2
    function = text[start:end]
    command = (
        function
        + "\n"
        + mock
        + "\ntry { Assert-IsoDismounted 'C:\\inputs.iso'; exit 0 }"
        + " catch { Write-Output $_.Exception.Message; exit 1 }"
    )
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command],
        text=True,
        capture_output=True,
        check=False,
    )


def test_roundtrip_verifier_uses_targeted_dismount_probe() -> None:
    text = ROUNDTRIP.read_text(encoding="utf-8")
    assert "Get-DiskImage -ImagePath $isoPath" in text
    assert "still mounted" in text.lower() or "remained mounted" in text.lower()
    assert "Dismount-DiskImage -ImagePath $isoPath" in text


def test_dismount_probe_fails_closed_for_query_error_and_not_found() -> None:
    if POWERSHELL is None:
        return
    for mock in (
        "function Get-DiskImage { throw 'query failed' }",
        "function Get-DiskImage { return $null }",
    ):
        result = _run_dismount_probe(mock)
        assert result.returncode != 0
        assert result.stdout.strip() or result.stderr.strip()


def test_dismount_probe_passes_only_for_explicit_detached_image() -> None:
    if POWERSHELL is None:
        return
    detached = _run_dismount_probe("function Get-DiskImage { [pscustomobject]@{ Attached = $false } }")
    assert detached.returncode == 0, detached.stdout + detached.stderr
    attached = _run_dismount_probe("function Get-DiskImage { [pscustomobject]@{ Attached = $true } }")
    assert attached.returncode != 0
