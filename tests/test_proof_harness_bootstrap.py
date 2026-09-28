"""Deterministic contracts for the reusable guest bootstrap watcher."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "proof-harness" / "guest" / "bootstrap-watch.ps1"
FIXTURES = ROOT / "proof-harness" / "fixtures"
FIXTURE_RUNNER = FIXTURES / "runner.ps1"
FIXTURE_SCENARIO = FIXTURES / "reusable-scenario.json"
FIXTURE_ARTIFACTS = FIXTURES / "expected-artifacts.json"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh.exe")


def _run_ps(command: str, *, timeout: float = 30) -> subprocess.CompletedProcess[str]:
    assert POWERSHELL is not None
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command],
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def _ps_path(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _dot_source() -> str:
    return ". " + _ps_path(BOOTSTRAP) + " -NoRun"


def _write_contract(root: Path, *, runner: str = "Write-Output 'harmless'\nexit 0\n") -> None:
    inputs = root / "inputs"
    evidence = root / "evidence"
    inputs.mkdir(parents=True)
    evidence.mkdir(parents=True)
    (inputs / "runner.ps1").write_text(runner, encoding="utf-8")
    (inputs / "scenario.json").write_text(
        json.dumps(
            {
                "schema": "gentle-ai.yasb-limitora.reusable-vm-run/v1",
                "scenario": "smoke",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256((inputs / "runner.ps1").read_bytes()).hexdigest()
    (inputs / "expected-runner.sha256").write_text(digest + "\n", encoding="utf-8")
    (inputs / "expected-artifacts.json").write_text(
        json.dumps(
            {
                "schema": "gentle-ai.yasb-limitora.reusable-artifact-manifest/v1",
                "artifacts": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_fixture_contract(root: Path) -> None:
    inputs = root / "inputs"
    evidence = root / "evidence"
    inputs.mkdir(parents=True)
    evidence.mkdir(parents=True)
    shutil.copyfile(FIXTURE_RUNNER, inputs / "runner.ps1")
    shutil.copyfile(FIXTURE_SCENARIO, inputs / "scenario.json")
    shutil.copyfile(FIXTURE_ARTIFACTS, inputs / "expected-artifacts.json")
    digest = hashlib.sha256((inputs / "runner.ps1").read_bytes()).hexdigest()
    (inputs / "expected-runner.sha256").write_text(digest + "\n", encoding="utf-8")


def test_bootstrap_is_new_universal_source_with_explicit_boundary() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert "S11BINPUTS" in text
    assert "S11BEVIDENCE" in text
    assert "runner.ps1" in text
    assert "scenario.json" in text
    assert "expected-runner.sha256" in text
    assert "expected-artifacts.json" in text
    assert "Resolve-UniqueVolume" in text
    assert "ReparsePoint" in text
    assert "Stop-Computer" in text
    assert "watch-scenarios.ps1" not in text
    assert ".iso" not in text.lower()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_volume_discovery_fails_closed_for_missing_and_ambiguous_labels() -> None:
    cases = [
        ("@()", "missing"),
        (
            "@([pscustomobject]@{Root='X:\\'; Label='S11BINPUTS'; VolumeId='one'; Ready=$true; Fixed=$true}, [pscustomobject]@{Root='Y:\\'; Label='S11BINPUTS'; VolumeId='two'; Ready=$true; Fixed=$true})",
            "ambiguous",
        ),
    ]
    for candidates, expected in cases:
        result = _run_ps(
            _dot_source()
            + f"\ntry {{ Resolve-UniqueVolume -Label 'S11BINPUTS' -Candidates {candidates}; exit 0 }}"
            + " catch { Write-Output $_.Exception.Message; exit 1 }"
        )
        assert result.returncode != 0
        assert expected in (result.stdout + result.stderr).lower()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_real_resolve_path_handles_discovery_cardinality_and_exact_labels() -> None:
    command = _dot_source() + r"""
function Get-CandidateVolumes {
    param([string] $Label)
    if ($Label -ceq 'S11BINPUTS') {
        $candidates = @([pscustomobject]@{Root='F:\'; Label='S11BINPUTS'; VolumeId='F:'; Ready=$true; Fixed=$true})
    } elseif ($Label -ceq 'S11BEVIDENCE') {
        $candidates = @([pscustomobject]@{Root='G:\'; Label='S11BEVIDENCE'; VolumeId='G:'; Ready=$true; Fixed=$true})
    } elseif ($Label -ceq 'AMBIGUOUS') {
        $candidates = @(
            [pscustomobject]@{Root='F:\'; Label='AMBIGUOUS'; VolumeId='F:'; Ready=$true; Fixed=$true}
            [pscustomobject]@{Root='G:\'; Label='AMBIGUOUS'; VolumeId='G:'; Ready=$true; Fixed=$true}
        )
    } else {
        $candidates = @()
    }
    return ,$candidates
}
$input = Resolve-UniqueVolume -Label 'S11BINPUTS'
$evidence = Resolve-UniqueVolume -Label 'S11BEVIDENCE'
Assert-DistinctVolumes $input $evidence
if ($input -ne 'F:\' -or $evidence -ne 'G:\') { throw "unexpected roots: $input / $evidence" }
$resolved = $false
try { Resolve-UniqueVolume -Label 'MISSING' | Out-Null; $resolved = $true } catch { if ($_.Exception.Message -notmatch 'missing') { throw } }
if ($resolved) { throw 'missing label unexpectedly resolved' }
$resolved = $false
try { Resolve-UniqueVolume -Label 'AMBIGUOUS' | Out-Null; $resolved = $true } catch { if ($_.Exception.Message -notmatch 'ambiguous') { throw } }
if ($resolved) { throw 'ambiguous label unexpectedly resolved' }
$resolved = $false
try { Resolve-UniqueVolume -Label 's11binputs' | Out-Null; $resolved = $true } catch { if ($_.Exception.Message -notmatch 'missing') { throw } }
if ($resolved) { throw 'case-folded label unexpectedly resolved' }
$resolved = $false
try { Assert-DistinctVolumes 'F:\' 'F:\'; $resolved = $true } catch { if ($_.Exception.Message -notmatch 'distinct') { throw } }
if ($resolved) { throw 'shared volume unexpectedly accepted' }
Write-Output 'resolved F:/G: missing ambiguous exact-case distinct'
"""
    result = _run_ps(command)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "resolved F:/G: missing ambiguous exact-case distinct" in result.stdout


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_harmless_runner_writes_bounded_success_evidence(tmp_path: Path) -> None:
    _write_fixture_contract(tmp_path)
    result = _run_ps(
        _dot_source()
        + "\nfunction Resolve-UniqueVolume { param([string]$Label, [object[]]$Candidates) "
        + f"if ($Label -eq 'S11BINPUTS') {{ return {_ps_path(tmp_path / 'inputs')} }} return {_ps_path(tmp_path / 'evidence')} }}"
        + "\nfunction Assert-DistinctVolumes { }"
        + "\nInvoke-BootstrapCycle -NoShutdown; exit 0"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    done = json.loads((tmp_path / "evidence" / "done.json").read_text(encoding="utf-8"))
    exit_record = json.loads((tmp_path / "evidence" / "exit.json").read_text(encoding="utf-8"))
    expected_bootstrap_hash = hashlib.sha256(BOOTSTRAP.read_bytes()).hexdigest()
    assert done["result"] == "success"
    assert done["runnerExitCode"] == 0
    assert done["bootstrapSha256"] == expected_bootstrap_hash
    assert exit_record["success"] is True
    artifact = tmp_path / "evidence" / "artifact.txt"
    assert artifact.stat().st_size == 23
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == "a65c40af2ddb17e3e5c65e30eb5abe70e0a70e34c02d244cf3c1af3e0ccc9db8"
    log = (tmp_path / "evidence" / "bootstrap.log").read_text(encoding="utf-8")
    assert f"bootstrap watcher sha256={expected_bootstrap_hash}" in log
    assert (tmp_path / "evidence" / "bootstrap.log").stat().st_size < 1024 * 1024


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_tree_digest_skips_only_protected_root_metadata_and_keeps_nested_names(tmp_path: Path) -> None:
    assert POWERSHELL is not None
    root = tmp_path / "inputs"
    (root / "System Volume Information").mkdir(parents=True)
    (root / "$RECYCLE.BIN").mkdir()
    (root / "nested" / "$RECYCLE.BIN").mkdir(parents=True)
    (root / "nested" / "$RECYCLE.BIN" / "kept.txt").write_text("nested\n", encoding="utf-8")
    (root / "System Volume Information" / "protected.txt").write_text("one\n", encoding="utf-8")
    command = (
        _dot_source()
        + "\nfunction Get-ChildItem { [CmdletBinding()] param([string]$LiteralPath, [switch]$Recurse, [switch]$Force) "
        + "if($Recurse){throw 'simulated protected root metadata access denied'} "
        + "Microsoft.PowerShell.Management\\Get-ChildItem -LiteralPath $LiteralPath -Force:$Force -ErrorAction Stop }"
        + f"\n$d1=Get-TreeDigest {_ps_path(root)}"
        + f"\n[IO.File]::WriteAllText({_ps_path(root / 'System Volume Information' / 'protected.txt')},'two')"
        + f"\n$d2=Get-TreeDigest {_ps_path(root)}"
        + f"\n[IO.File]::WriteAllText({_ps_path(root / 'nested' / '$RECYCLE.BIN' / 'kept.txt')},'changed')"
        + f"\n$d3=Get-TreeDigest {_ps_path(root)}; Write-Output ($d1+' '+$d2+' '+$d3); exit 0"
    )
    result = _run_ps(command)
    assert result.returncode == 0, result.stdout + result.stderr
    digests = result.stdout.strip().split()
    assert len(digests) == 3
    assert digests[0] == digests[1]
    assert digests[1] != digests[2]


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_authored_runner_mutation_is_rejected_by_input_digest(tmp_path: Path) -> None:
    runner = "param([string]$EvidenceRoot, [string]$ScenarioPath)\n[IO.File]::WriteAllText((Join-Path (Split-Path -Parent $ScenarioPath) 'runner-mutated.txt'), 'tampered')\nexit 0\n"
    _write_contract(tmp_path, runner=runner)
    result = _run_ps(
        _dot_source()
        + "\nfunction Resolve-UniqueVolume { param([string]$Label, [object[]]$Candidates) "
        + f"if ($Label -eq 'S11BINPUTS') {{ return {_ps_path(tmp_path / 'inputs')} }} return {_ps_path(tmp_path / 'evidence')} }}"
        + "\nfunction Assert-DistinctVolumes { }"
        + "\ntry { Invoke-BootstrapCycle -NoShutdown; exit 0 } catch { exit 1 }"
    )
    assert result.returncode != 0
    evidence = tmp_path / "evidence"
    failure = json.loads((evidence / "done.json").read_text(encoding="utf-8"))
    assert failure["result"] == "failed"
    assert "input volume changed" in failure["failure"]


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
@pytest.mark.parametrize(
    ("case", "runner", "remove_expected_hash"),
    [
        ("mismatch", "exit 0\n", False),
        ("nonzero", "exit 23\n", False),
        ("missing", "exit 0\n", True),
    ],
)
def test_contract_failures_write_explicit_failure_evidence(
    tmp_path: Path, case: str, runner: str, remove_expected_hash: bool
) -> None:
    root = tmp_path / case
    _write_contract(root, runner=runner)
    if case == "mismatch":
        (root / "inputs" / "expected-runner.sha256").write_text("0" * 64 + "\n", encoding="utf-8")
    if remove_expected_hash:
        (root / "inputs" / "expected-runner.sha256").unlink()
    result = _run_ps(
        _dot_source()
        + "\nfunction Resolve-UniqueVolume { param([string]$Label, [object[]]$Candidates) "
        + f"if ($Label -eq 'S11BINPUTS') {{ return {_ps_path(root / 'inputs')} }} return {_ps_path(root / 'evidence')} }}"
        + "\nfunction Assert-DistinctVolumes { }"
        + "\ntry { Invoke-BootstrapCycle -NoShutdown; exit 0 } catch { exit 1 }"
    )
    assert result.returncode != 0
    exit_record = json.loads((root / "evidence" / "exit.json").read_text(encoding="utf-8"))
    assert exit_record["success"] is False
    assert exit_record["failure"]
    assert exit_record["runnerExitCode"] != 0 or case in {"mismatch", "missing"}
    assert json.loads((root / "evidence" / "done.json").read_text(encoding="utf-8"))["result"] == "failed"


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_runner_streams_both_output_channels_to_bounded_files(tmp_path: Path) -> None:
    runner = tmp_path / "runner.ps1"
    stdout_path = tmp_path / "stdout.txt"
    stderr_path = tmp_path / "stderr.txt"
    runner.write_text(
        "1..12000 | ForEach-Object { Write-Output ('stdout-' + $_); [Console]::Error.WriteLine('stderr-' + $_) }\nexit 0\n",
        encoding="utf-8",
    )
    result = _run_ps(
        _dot_source()
        + f"\n$code=Invoke-Runner -RunnerPath {_ps_path(runner)} -ScenarioPath {_ps_path(runner)}"
        + f" -EvidenceRoot {_ps_path(tmp_path)} -StdoutPath {_ps_path(stdout_path)}"
        + f" -StderrPath {_ps_path(stderr_path)} -TimeoutSeconds 10; Write-Output ('exit=' + $code); exit 0",
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "exit=0" in result.stdout
    assert "stdout-" in stdout_path.read_text(encoding="utf-8")
    assert "stderr-" in stderr_path.read_text(encoding="utf-8")
    assert stdout_path.stat().st_size < 2 * 1024 * 1024
    assert stderr_path.stat().st_size < 2 * 1024 * 1024


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_hanging_runner_is_killed_by_bounded_timeout(tmp_path: Path) -> None:
    runner = tmp_path / "runner.ps1"
    stdout_path = tmp_path / "stdout.txt"
    stderr_path = tmp_path / "stderr.txt"
    runner.write_text("Start-Sleep -Seconds 30\nexit 0\n", encoding="utf-8")
    result = _run_ps(
        _dot_source()
        + f"\n$code=Invoke-Runner -RunnerPath {_ps_path(runner)} -ScenarioPath {_ps_path(runner)}"
        + f" -EvidenceRoot {_ps_path(tmp_path)} -StdoutPath {_ps_path(stdout_path)}"
        + f" -StderrPath {_ps_path(stderr_path)} -TimeoutSeconds 2; Write-Output ('exit=' + $code); exit 0",
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "exit=124" in result.stdout


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable")
def test_bootstrap_has_no_power_shell_ast_errors() -> None:
    command = (
        "$tokens=$null;$errors=$null;"
        + f"[System.Management.Automation.Language.Parser]::ParseFile({_ps_path(BOOTSTRAP)}, [ref]$tokens, [ref]$errors) | Out-Null;"
        + "if ($errors.Count -ne 0) { $errors | ForEach-Object { Write-Output $_ }; exit 1 }; exit 0"
    )
    result = _run_ps(command)
    assert result.returncode == 0, result.stdout + result.stderr
