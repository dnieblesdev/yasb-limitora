"""Offline host-contract tests for the reusable VM harness."""

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "proof-harness" / "host"
RUNNER = HOST / "run-reusable-vm.ps1"
VOLUMES = HOST / "new-run-volumes.ps1"
VERIFIER = HOST / "verify-reusable-evidence.py"
FIXTURES = ROOT / "proof-harness" / "fixtures"
RUN_SCENARIO = FIXTURES / "reusable-scenario.json"
EXPECTED_ARTIFACTS = FIXTURES / "expected-artifacts.json"
BOOTSTRAP = ROOT / "proof-harness" / "guest" / "bootstrap-watch.ps1"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh.exe")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_digest(root: Path) -> str:
    entries = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            entries.append(f"{path.relative_to(root).as_posix()}|{path.stat().st_size}|{_sha(path)}")
    return hashlib.sha256(("\n".join(entries) + "\n").encode()).hexdigest()


def _ps_path(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _make_contract(tmp_path: Path) -> tuple[Path, Path]:
    assert POWERSHELL is not None
    input_root = tmp_path / "input"
    evidence_root = tmp_path / "evidence"
    input_root.mkdir()
    evidence_root.mkdir()
    runner = input_root / "runner.ps1"
    artifact_bytes = b"guest-nested-artifact/v1\n"
    runner.write_text(
        "param([string]$EvidenceRoot, [string]$ScenarioPath)\n"
        "$artifactPath = Join-Path $EvidenceRoot 'nested\\artifact.txt'\n"
        "New-Item -ItemType Directory -Path (Split-Path -Parent $artifactPath) | Out-Null\n"
        "[IO.File]::WriteAllText($artifactPath, \"guest-nested-artifact/v1`n\", [Text.UTF8Encoding]::new($false))\n"
        "exit 0\n",
        encoding="utf-8",
    )
    (input_root / "scenario.json").write_text(
        json.dumps({"schema": "gentle-ai.yasb-limitora.reusable-vm-run/v1", "scenario": "offline-smoke"}) + "\n",
        encoding="utf-8",
    )
    (input_root / "expected-runner.sha256").write_text(_sha(runner) + "\n", encoding="utf-8")
    (input_root / "expected-artifacts.json").write_text(
        json.dumps(
            {
                "schema": "gentle-ai.yasb-limitora.reusable-artifact-manifest/v1",
                "artifacts": [{"path": "nested/artifact.txt", "size": len(artifact_bytes), "sha256": hashlib.sha256(artifact_bytes).hexdigest()}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    command = (
        f". {_ps_path(BOOTSTRAP)} -NoRun; "
        "function Resolve-UniqueVolume { param([string]$Label, [object[]]$Candidates) "
        f"if($Label -eq 'S11BINPUTS'){{return {_ps_path(input_root)}}} return {_ps_path(evidence_root)} }}; "
        "function Assert-DistinctVolumes { }; function Stop-Computer { }; Invoke-BootstrapCycle | Out-Null"
    )
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (evidence_root / "done.json").is_file()
    assert (evidence_root / "exit.json").is_file()
    done = json.loads((evidence_root / "done.json").read_text(encoding="utf-8"))
    exit_record = json.loads((evidence_root / "exit.json").read_text(encoding="utf-8"))
    assert exit_record["runnerExitCode"] == 0
    assert done["artifacts"][0]["path"] == r"nested\artifact.txt"
    return input_root, evidence_root


def _verify(input_root: Path, evidence_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python",
            str(VERIFIER),
            str(evidence_root),
            "--input-root",
            str(input_root),
            "--expected-bootstrap-sha256",
            _sha(BOOTSTRAP),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_reusable_evidence_passes_from_guest_producer(tmp_path: Path) -> None:
    input_root, evidence_root = _make_contract(tmp_path)
    result = _verify(input_root, evidence_root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "VERDICT: PASS" in result.stdout
    assert "input_tree_sha256=" in result.stdout


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
@pytest.mark.parametrize("tamper", ["runner", "artifact", "exit", "input", "bootstrap"])
def test_reusable_evidence_rejects_each_hash_tamper(tmp_path: Path, tamper: str) -> None:
    input_root, evidence_root = _make_contract(tmp_path)
    if tamper == "runner":
        (input_root / "runner.ps1").write_text("tampered\n", encoding="utf-8")
    elif tamper == "artifact":
        (evidence_root / "nested" / "artifact.txt").write_text("tampered\n", encoding="utf-8")
    elif tamper == "input":
        (input_root / "scenario.json").write_text("tampered\n", encoding="utf-8")
    elif tamper == "bootstrap":
        (evidence_root / "bootstrap.log").write_text("bootstrap watcher sha256=" + "0" * 64 + "\n", encoding="utf-8")
    else:
        exit_record = json.loads((evidence_root / "exit.json").read_text(encoding="utf-8"))
        exit_record["runnerExitCode"] = 23
        (evidence_root / "exit.json").write_text(json.dumps(exit_record) + "\n", encoding="utf-8")
    result = _verify(input_root, evidence_root)
    assert result.returncode != 0
    assert "VERDICT: FAIL" in result.stdout
    if tamper == "bootstrap":
        assert "bootstrap" in result.stdout.lower()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_verifier_rejects_mismatched_host_checkpoint_id(tmp_path: Path) -> None:
    input_root, evidence_root = _make_contract(tmp_path)
    runner_hash = _sha(input_root / "runner.ps1")
    checkpoint = {"Name": "generic", "Id": "checkpoint-1", "VMId": "vm-1", "CreationTime": "2026-01-01T00:00:00.0000000Z"}
    provenance = {
        "schema": "gentle-ai.yasb-limitora.reusable-vm-host-provenance/v1",
        "runId": "run-1",
        "vmName": "fake",
        "requestedCheckpointName": "generic",
        "requestedCheckpointId": "checkpoint-1",
        "requestedCheckpointVmId": "vm-1",
        "requestedCheckpointCreationTimeUtc": checkpoint["CreationTime"],
        "checkpointBeforeRestore": checkpoint,
        "checkpointAfterRestore": dict(checkpoint),
        "restoreObservedUtc": "2026-01-01T00:00:01.0000000Z",
        "bootstrapSha256": _sha(BOOTSTRAP),
        "runnerSha256": runner_hash,
        "inputVhdxSha256": "a" * 64,
        "outcomes": {"checkpointRestore": "success", "guestRun": "success", "evidenceExtraction": "success", "verification": "success", "overall": "success"},
    }
    path = tmp_path / "host-provenance.json"
    path.write_text(json.dumps(provenance) + "\n", encoding="utf-8")
    result = subprocess.run(
        ["python", str(VERIFIER), str(evidence_root), "--input-root", str(input_root), "--expected-bootstrap-sha256", _sha(BOOTSTRAP), "--host-provenance", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    provenance["checkpointAfterRestore"]["Id"] = "checkpoint-2"
    path.write_text(json.dumps(provenance) + "\n", encoding="utf-8")
    result = subprocess.run(
        ["python", str(VERIFIER), str(evidence_root), "--input-root", str(input_root), "--expected-bootstrap-sha256", _sha(BOOTSTRAP), "--host-provenance", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert "checkpoint identity drift" in result.stdout.lower()


def test_verifier_rejects_missing_guest_exit_runner_code(tmp_path: Path) -> None:
    input_root, evidence_root = _make_contract(tmp_path)
    exit_record = json.loads((evidence_root / "exit.json").read_text(encoding="utf-8"))
    del exit_record["runnerExitCode"]
    (evidence_root / "exit.json").write_text(json.dumps(exit_record) + "\n", encoding="utf-8")
    result = _verify(input_root, evidence_root)
    assert result.returncode != 0
    assert "runner exit mismatch" in result.stdout.lower()


def test_host_scripts_use_exact_labels_and_no_legacy_media_path() -> None:
    run_text = RUNNER.read_text(encoding="utf-8").lower()
    volume_text = VOLUMES.read_text(encoding="utf-8").lower()
    for text in (run_text, volume_text):
        assert "s11binputs" in text
        assert "s11bevidence" in text
        assert "dryrun" in text
        assert "orchestrate-lifecycle" not in text
        assert "set-vmdvddrive" not in text
        assert "mount-vmdvd" not in text
        assert "enter-pssession" not in text
        assert "invoke-command" not in text
    assert re.search(r"new-uniquerundirectory[^\n]+\('run-' \+ \$runid\)", run_text)
    assert re.search(r"new-uniquerundirectory[^\n]+\('failed-' \+ \$runid\)", run_text)


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_tree_digest_skips_only_protected_root_metadata(tmp_path: Path) -> None:
    assert POWERSHELL is not None
    root = tmp_path / "input"
    (root / "System Volume Information").mkdir(parents=True)
    (root / "$RECYCLE.BIN").mkdir()
    (root / "nested" / "System Volume Information").mkdir(parents=True)
    (root / "nested" / "System Volume Information" / "kept.txt").write_text("nested\n", encoding="utf-8")
    (root / "runner.ps1").write_text("runner\n", encoding="utf-8")
    (root / "System Volume Information" / "protected.txt").write_text("one\n", encoding="utf-8")
    command = (
        f". '{VOLUMES}' -RunnerPath '{FIXTURES / 'runner.ps1'}' -ScenarioPath '{RUN_SCENARIO}' -ExpectedArtifactsPath '{EXPECTED_ARTIFACTS}' -InputVhdxPath '{tmp_path / 'inputs.vhdx'}' -EvidenceVhdxPath '{tmp_path / 'evidence.vhdx'}' -NoRun; "
        "function Get-ChildItem { [CmdletBinding()] param([string]$LiteralPath, [switch]$Recurse, [switch]$Force) "
        "if($Recurse){throw 'simulated protected root metadata access denied'} "
        "Microsoft.PowerShell.Management\\Get-ChildItem -LiteralPath $LiteralPath -Force:$Force -ErrorAction Stop }; "
        f"$d1=Get-InputTreeDigest '{root}'; "
        f"[IO.File]::WriteAllText('{root / 'System Volume Information' / 'protected.txt'}','two'); "
        f"$d2=Get-InputTreeDigest '{root}'; "
        f"[IO.File]::WriteAllText('{root / 'nested' / 'System Volume Information' / 'kept.txt'}','changed'); "
        f"$d3=Get-InputTreeDigest '{root}'; Write-Output ($d1+' '+$d2+' '+$d3)"
    )
    result = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command], text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    digests = result.stdout.strip().split()
    assert len(digests) == 3
    assert digests[0] == digests[1]
    assert digests[1] != digests[2]


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_optional_input_rejects_reserved_volume_root_name(tmp_path: Path) -> None:
    assert POWERSHELL is not None
    runner = FIXTURES / "runner.ps1"
    reserved = tmp_path / "System Volume Information"
    reserved.mkdir()
    command = (
        f". '{VOLUMES}' -RunnerPath '{runner}' -ScenarioPath '{RUN_SCENARIO}' -ExpectedArtifactsPath '{EXPECTED_ARTIFACTS}' -InputVhdxPath '{tmp_path / 'inputs.vhdx'}' -EvidenceVhdxPath '{tmp_path / 'evidence.vhdx'}' -NoRun; "
        f"try {{ Get-ValidatedInputContract '{runner}' '{RUN_SCENARIO}' '{EXPECTED_ARTIFACTS}' @('{reserved}'); exit 1 }} "
        "catch { if($_.Exception.Message -notmatch 'reserved|System Volume Information'){ Write-Output $_.Exception.Message; exit 2 }; exit 0 }"
    )
    result = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command], text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_default_mode_refuses_untrusted_writable_input(tmp_path: Path) -> None:
    assert POWERSHELL is not None
    command = (
        f". '{RUNNER}' -VmName fake -CheckpointName generic -RunnerPath '{FIXTURES / 'runner.ps1'}' "
        f"-ScenarioPath '{RUN_SCENARIO}' -ExpectedArtifactsPath '{EXPECTED_ARTIFACTS}' "
        f"-VhdxDirectory '{tmp_path / 'vhdx'}' -EvidenceDirectory '{tmp_path / 'evidence'}' -VerifierPath '{VERIFIER}' -NoRun; "
        f"try {{ Invoke-ReusableRun -Name fake -Checkpoint generic -Runner '{FIXTURES / 'runner.ps1'}' -Scenario '{RUN_SCENARIO}' "
        f"-ExpectedArtifacts '{EXPECTED_ARTIFACTS}' -VhdxRoot '{tmp_path / 'vhdx'}' -EvidenceRoot '{tmp_path / 'evidence'}' -DryRun:$false; exit 1 }} "
        "catch { if($_.Exception.Message -notmatch 'read-only.*unavailable|AllowWritableInputIntegrityFallback'){exit 2}; exit 0 }"
    )
    result = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command], text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (tmp_path / "vhdx").exists()
    assert not (tmp_path / "evidence").exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_mocked_volume_stage_is_called_once(tmp_path: Path) -> None:
    assert POWERSHELL is not None
    command = (
        f". '{RUNNER}' -VmName fake -CheckpointName generic -RunnerPath '{FIXTURES / 'runner.ps1'}' "
        f"-ScenarioPath '{RUN_SCENARIO}' -ExpectedArtifactsPath '{EXPECTED_ARTIFACTS}' "
        f"-VhdxDirectory '{tmp_path / 'vhdx'}' -EvidenceDirectory '{tmp_path / 'evidence'}' -VerifierPath '{VERIFIER}' -BootstrapPath '{BOOTSTRAP}' -NoRun; "
        "$global:volumeCalls=0; function New-RunVolumes { $global:volumeCalls++; if($global:volumeCalls -gt 1){throw 'second volume stage'}; return [ordered]@{inputTreeSha256='a'} }; "
        "function Restore-SameGenericCheckpoint { throw 'stop-after-stage' }; "
        f"try {{ Invoke-ReusableRun -Name fake -Checkpoint generic -Runner '{FIXTURES / 'runner.ps1'}' -Scenario '{RUN_SCENARIO}' "
        f"-ExpectedArtifacts '{EXPECTED_ARTIFACTS}' -VhdxRoot '{tmp_path / 'vhdx'}' -EvidenceRoot '{tmp_path / 'evidence'}' -AllowWritableFallback:$true; }} catch {{ }}; "
        "Write-Output ('volumeCalls=' + $global:volumeCalls); if($global:volumeCalls -ne 1){exit 1}"
    )
    result = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command], text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "volumeCalls=1" in result.stdout


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_dry_run_calls_no_hyperv_cmdlets(tmp_path: Path) -> None:
    assert POWERSHELL is not None
    command = (
        f"& '{RUNNER}' -VmName fake -CheckpointName generic -RunnerPath '{FIXTURES / 'runner.ps1'}' "
        f"-ScenarioPath '{RUN_SCENARIO}' -ExpectedArtifactsPath '{EXPECTED_ARTIFACTS}' "
        f"-VhdxDirectory '{tmp_path / 'vhdx'}' -EvidenceDirectory '{tmp_path / 'evidence'}' -DryRun"
    )
    result = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command], text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    plan = json.loads(result.stdout)
    assert plan["result"] == "planned"
    assert plan["inputLabel"] == "S11BINPUTS"
    assert plan["evidenceLabel"] == "S11BEVIDENCE"
    assert "New-VHD" not in result.stdout + result.stderr
    assert not (tmp_path / "vhdx").exists()
    assert not (tmp_path / "evidence").exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_restore_rejects_checkpoint_identity_drift(tmp_path: Path) -> None:
    assert POWERSHELL is not None
    command = (
        f". '{RUNNER}' -VmName fake -CheckpointName generic -RunnerPath '{FIXTURES / 'runner.ps1'}' "
        f"-ScenarioPath '{RUN_SCENARIO}' -ExpectedArtifactsPath '{EXPECTED_ARTIFACTS}' "
        f"-VhdxDirectory '{tmp_path / 'vhdx'}' -EvidenceDirectory '{tmp_path / 'evidence'}' -NoRun; "
        "function Get-VM { [pscustomobject]@{ State = 'Off' } }; "
        "$script:checkpointCall = 0; "
        "function Get-VMCheckpoint { $script:checkpointCall++; "
        "if($script:checkpointCall -eq 1) { return [pscustomobject]@{ Name='generic'; Id='checkpoint-1'; VMId='vm-1'; CreationTime=[DateTime]'2026-01-01T00:00:00Z' } } "
        "return [pscustomobject]@{ Name='generic'; Id='checkpoint-2'; VMId='vm-1'; CreationTime=[DateTime]'2026-01-01T00:00:00Z' } }; "
        "function Restore-VMCheckpoint { param([Parameter(ValueFromPipeline=$true)]$InputObject, [switch]$Confirm); process { } }; "
        "function Start-VM { }; function Wait-ForVmState { return 'Running' }; "
        "try { Restore-SameGenericCheckpoint -Name fake -Checkpoint generic; exit 1 } "
        "catch { if($_.Exception.Message -notmatch 'checkpoint.*identity|drift|mismatch') { Write-Output $_.Exception.Message; exit 2 }; exit 0 }"
    )
    result = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command], text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_source_scripts_are_present_and_versioned() -> None:
    assert RUNNER.is_file()
    assert VOLUMES.is_file()
    assert VERIFIER.is_file()
    assert "reusable-vm" in RUNNER.read_text(encoding="utf-8")
