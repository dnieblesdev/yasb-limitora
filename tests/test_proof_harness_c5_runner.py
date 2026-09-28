"""C5 guest runner, fixture, and source-custody contract tests."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "proof-harness"
RUNNER = HARNESS / "guest" / "run-c5-silent-uninstall.ps1"
C5 = HARNESS / "fixtures" / "c5"
SCENARIO = C5 / "scenario.json"
C5_STEPS = C5 / "c5-steps.json"
EXPECTED_ARTIFACTS = C5 / "expected-artifacts.json"
STAGER = HARNESS / "host" / "new-run-volumes.ps1"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
FIXTURE_SHA256 = "e16c422f5a2593dd4bfcc1cf5979cfad382769422953ff10202986be8f0a1795"
SCENARIO_SHA256 = "8aca8127167fc5ec0ec143c563e1b14c1d77bf763c8203d2095bd1c515a37c93"
SETUP_NAME = "yasb-limitora-0.2.0-setup.exe"


def test_c5_fixture_declares_legacy_binding_and_exact_setup_and_fixture_identity() -> None:
    scenario = json.loads(SCENARIO.read_text(encoding="utf-8"))
    steps = json.loads(C5_STEPS.read_text(encoding="utf-8"))
    assert scenario == {
        "schema": "gentle-ai.yasb-limitora.reusable-vm-run/v1",
        "scenario": "silent-uninstall-with-state-root",
        "dialogAnswers": [],
    }
    assert steps["scenario"] == "silent-uninstall-with-state-root"
    assert steps["schema"] == "gentle-ai.yasb-limitora.c5-silent-uninstall/v1"
    assert steps["legacyScenarioSha256"] == SCENARIO_SHA256
    assert steps["setup"] == {"name": SETUP_NAME, "size": 11054574, "sha256": "1d58f3618f5b22ddccacc7be2dcf8e3a1e9a90dba57dffe431d8ca8ae6df3394"}
    assert steps["silentArguments"] == ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
    assert steps["dialogAnswers"] == []
    assert {entry["sha256"] for entry in steps["fixtureFiles"]} == {FIXTURE_SHA256}
    assert all(entry["size"] == 32 for entry in steps["fixtureFiles"])


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_c5_contract_passes_real_stager_dry_run(tmp_path: Path) -> None:
    assert POWERSHELL is not None
    command = (
        f"& '{STAGER}' -RunnerPath '{RUNNER}' -ScenarioPath '{SCENARIO}' "
        f"-ExpectedArtifactsPath '{EXPECTED_ARTIFACTS}' -InputVhdxPath '{tmp_path / 'inputs.vhdx'}' "
        f"-EvidenceVhdxPath '{tmp_path / 'evidence.vhdx'}' -AdditionalInputPath @('{C5_STEPS}', '{HARNESS / 'guest' / 'capture-state.ps1'}', '{C5 / 'state-root'}') -DryRun"
    )
    result = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command], text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    plan = json.loads(result.stdout)
    assert plan["inputLabel"] == "S11BINPUTS"
    assert "c5-steps.json" in plan["inputFiles"]
    assert "scenario.json" in plan["inputFiles"]
    assert not (tmp_path / "inputs.vhdx").exists()
    assert not (tmp_path / "evidence.vhdx").exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_c5_runner_binds_process_and_capture_calls_to_evidence_root() -> None:
    assert POWERSHELL is not None
    command = f"""
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{RUNNER}', [ref]$tokens, [ref]$errors)
if ($errors.Count -ne 0) {{ Write-Output 'runner parse failed'; exit 2 }}
$bad = @($ast.FindAll({{
    param($node)
    if ($node -isnot [System.Management.Automation.Language.CommandAst]) {{ return $false }}
    if ($node.GetCommandName() -notin @('Invoke-C5Process', 'Invoke-Capture')) {{ return $false }}
    return @($node.CommandElements | Where-Object {{ $_ -is [System.Management.Automation.Language.VariableExpressionAst] -and $_.VariablePath.UserPath -eq 'Evidence' }}).Count -gt 0
}}, $true))
if ($bad.Count -gt 0) {{ Write-Output 'undefined Evidence variable passed to process/capture call'; exit 1 }}
exit 0
"""
    result = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command], text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_c5_process_captures_identity_before_self_deleting_fixture_exits(tmp_path: Path) -> None:
    assert POWERSHELL is not None
    root = tmp_path / "process-fixture"
    evidence = tmp_path / "evidence"
    root.mkdir()
    evidence.mkdir()
    fixture = root / "self-delete.ps1"
    fixture.write_text("[IO.File]::Delete($PSCommandPath)\nexit 0\n", encoding="utf-8")
    command = f"""
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{RUNNER}', [ref]$tokens, [ref]$errors)
if ($errors.Count -ne 0) {{ throw 'runner parse failed' }}
function Get-FileHash {{ param([string] $LiteralPath, [string] $Algorithm) $sha = [Security.Cryptography.SHA256]::Create(); try {{ [pscustomobject]@{{ Hash = ([BitConverter]::ToString($sha.ComputeHash([IO.File]::ReadAllBytes($LiteralPath)))).Replace('-', '') }} }} finally {{ $sha.Dispose() }} }}
function Start-Process {{ param([string] $FilePath, [object[]] $ArgumentList, [string] $WorkingDirectory, [string] $RedirectStandardOutput, [string] $RedirectStandardError, [switch] $PassThru, [switch] $Wait) $child = Microsoft.PowerShell.Management\\Start-Process -FilePath 'powershell.exe' -ArgumentList (@('-NoProfile', '-NonInteractive', '-File', $FilePath) + @($ArgumentList)) -WorkingDirectory $WorkingDirectory -RedirectStandardOutput $RedirectStandardOutput -RedirectStandardError $RedirectStandardError -PassThru -Wait; return [pscustomobject]@{{ ExitCode = [int]$child.ExitCode }} }}
foreach ($name in @('Get-Hash', 'Write-ExclusiveJson', 'Assert-ExitCode', 'Invoke-C5Process')) {{
    $definition = @($ast.FindAll({{ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name }}, $true) | Select-Object -First 1)
    if ($definition.Count -eq 0) {{ throw \"missing helper $name\" }}
    . ([scriptblock]::Create($definition[0].Extent.Text))
}}
$ScenarioName = 'silent-uninstall-with-state-root'
$record = Invoke-C5Process 'uninstall' 'uninstall' '{fixture}' @('/fixture') '{root}' '{evidence}'
if (Test-Path -LiteralPath '{fixture}') {{ throw 'self-deleting fixture still exists' }}
if ($record.executable.present -ne $true) {{ throw 'pre-execution presence was not recorded' }}
if ($record.executable.size -ne {fixture.stat().st_size}) {{ throw \"unexpected pre-execution size: $($record.executable.size)\" }}
if ($record.exitCode -ne 0) {{ throw \"unexpected exit: $($record.exitCode)\" }}
Write-Output (($record.executable.sha256) + ' ' + $record.executable.path)
"""
    result = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command], text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert str(fixture) in result.stdout


def test_c5_runner_is_guest_only_and_uses_two_argument_boundary() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    assert "param(" in text
    assert "[string] $EvidenceRoot" in text and "[string] $ScenarioPath" in text
    assert "capture-state.ps1" in text
    assert "c5-steps.json" in text
    assert "gentle-ai.yasb-limitora.reusable-vm-run/v1" in text
    assert "Start-Process" in text
    assert "SUPPRESSMSGBOXES" in text
    assert "dialogObserved" not in text
    assert "Get-VM" not in text and "New-VHD" not in text and "setup.exe" in text
    assert "1d58f3618f5b22ddccacc7be2dcf8e3a1e9a90dba57dffe431d8ca8ae6df3394" in text


def test_c5_artifact_manifest_is_deterministic_and_declares_result() -> None:
    manifest = json.loads(EXPECTED_ARTIFACTS.read_text(encoding="utf-8"))
    assert manifest["schema"] == "gentle-ai.yasb-limitora.reusable-artifact-manifest/v1"
    assert manifest["artifacts"][0]["path"] == "c5-result.json"
    raw = EXPECTED_ARTIFACTS.read_bytes()
    assert raw.replace(b"\r\n", b"\n") == json.dumps(manifest, indent=2).encode() + b"\n"


def test_frozen_bootstrap_is_not_modified() -> None:
    bootstrap = HARNESS / "guest" / "bootstrap-watch.ps1"
    assert hashlib.sha256(bootstrap.read_bytes()).hexdigest() == "35c216859790fb91ae310d39545e7499ceb8361f5624e5c72529fb400d8a80d7"
