"""Functional tests for exclusive pytest temp-root custody in the Windows runner."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


_FUNCTIONS = Path(__file__).parents[1] / ".github" / "workflows" / "windows-proof-functions.ps1"
_POWERSHELL = Path(os.environ["SystemRoot"]) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"


def _run_powershell(tmp_path: Path, body: str) -> subprocess.CompletedProcess[str]:
    command = f". '{_FUNCTIONS}';\n{body}"
    return subprocess.run(
        [str(_POWERSHELL), "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def test_exclusive_allocator_rejects_collision_reparse_and_failed_creation(tmp_path: Path) -> None:
    result = _run_powershell(
        tmp_path,
        """
$parent = Join-Path (Get-Location).Path 'allocator'
[IO.Directory]::CreateDirectory($parent) | Out-Null
$candidate = Join-Path $parent 'exclusive'
$first = New-ExclusivePytestTempRoot -Path $candidate
if (-not (Test-Path -LiteralPath $first -PathType Container)) { throw 'root missing' }
$second = New-ExclusivePytestTempRoot -Path (Join-Path $parent 'second')
if ($first -eq $second) { throw 'roots reused' }
try { New-ExclusivePytestTempRoot -Path $candidate; throw 'collision accepted' }
catch { if ($_.Exception.Message -eq 'collision accepted') { throw } }
$file = Join-Path $parent 'existing-file'
[IO.File]::WriteAllText($file, 'fixture')
try { New-ExclusivePytestTempRoot -Path $file; throw 'file collision accepted' }
catch { if ($_.Exception.Message -eq 'file collision accepted') { throw } }
$target = Join-Path $parent 'target'
[IO.Directory]::CreateDirectory($target) | Out-Null
$link = Join-Path $parent 'link'
New-Item -ItemType Junction -Path $link -Target $target | Out-Null
try { New-ExclusivePytestTempRoot -Path (Join-Path $link 'child'); throw 'reparse accepted' }
catch { if ($_.Exception.Message -eq 'reparse accepted') { throw } }
$failed = Join-Path $parent 'failed'
$failCreate = { param($path) return $false }
try { New-ExclusivePytestTempRoot -Path $failed -CreateDirectory $failCreate; throw 'allocation failure accepted' }
catch { if ($_.Exception.Message -eq 'allocation failure accepted') { throw } }
if (Test-Path -LiteralPath $failed) { throw 'failed allocation created a root' }
$race = Join-Path $parent 'race'
$raceCreate = { param($path) [IO.Directory]::CreateDirectory($path) | Out-Null; return $false }
try { New-ExclusivePytestTempRoot -Path $race -CreateDirectory $raceCreate; throw 'raced allocation accepted' }
catch { if ($_.Exception.Message -eq 'raced allocation accepted') { throw } }
if (-not (Test-Path -LiteralPath $race -PathType Container)) { throw 'race fixture missing' }
""",
    )
    assert result.returncode == 0, result.stderr


def test_runner_sets_child_only_root_and_preserves_exit_and_parent_environment(tmp_path: Path) -> None:
    result = _run_powershell(
        tmp_path,
        r"""
$envBefore = $env:PYTEST_DEBUG_TEMPROOT
$pythonBefore = $env:PYTHONUTF8
$env:pythonLocation = (Get-Location).Path
[IO.File]::WriteAllText((Join-Path $env:pythonLocation 'python.exe'), '')
function Invoke-CimMethod {
  param($ClassName, $MethodName, $Arguments, $ErrorAction)
  $global:launchCalled = $true
  $launcherPath = [regex]::Match($Arguments.CommandLine, '-File "([^"]+)"').Groups[1].Value
  $launcher = [IO.File]::ReadAllText($launcherPath)
  $rootMatch = [regex]::Match($launcher, "PYTEST_DEBUG_TEMPROOT = '([^']+)'")
  if (-not $rootMatch.Success) { throw 'child temp root absent' }
  $global:observedRoot = $rootMatch.Groups[1].Value
  if (-not (Test-Path -LiteralPath $global:observedRoot -PathType Container)) { throw 'child temp root absent' }
  if ($launcher -notmatch '\$pytestArguments = @\(' -or $launcher -notmatch 'tests/test_windows_native_proof.py' -or $launcher -notmatch '--junitxml=native-proof.xml') { throw 'pytest launch contract changed' }
  $exitName = [regex]::Match($launcher, '\$exitPath = Join-Path \$workspace "([^"]+)').Groups[1].Value
  [IO.File]::WriteAllText((Join-Path (Get-Location).Path $exitName), "7`r`n")
  return [PSCustomObject]@{ ReturnValue = 0; ProcessId = 123 }
}
function Get-Process { param($Id, $ErrorAction); return $null }
$value = Invoke-NativePytestWmi -Mode selected -Phase Probe -RawLogName native-proof.raw.log
if ($value -ne 7) { throw 'exit changed' }
if ($env:PYTEST_DEBUG_TEMPROOT -ne $envBefore -or $env:PYTHONUTF8 -ne $pythonBefore) { throw 'parent environment changed' }
if (-not (Test-Path -LiteralPath $global:observedRoot -PathType Container)) { throw 'runner cleaned namespace' }
""",
    )
    assert result.returncode == 0, result.stderr


def test_runner_does_not_spawn_when_namespace_allocation_fails(tmp_path: Path) -> None:
    result = _run_powershell(
        tmp_path,
        """
$env:pythonLocation = (Get-Location).Path
[IO.File]::WriteAllText((Join-Path $env:pythonLocation 'python.exe'), '')
function Invoke-CimMethod { [IO.File]::WriteAllText('spawned.marker', 'spawned') }
$failAllocation = { param($path) return $false }
$refusal = $null
try { Invoke-NativePytestWmi -Mode selected -Phase Probe -RawLogName native-proof.raw.log -CreatePytestDirectory $failAllocation }
catch { $refusal = $_.Exception.Message }
if ($refusal -ne 'Probe pytest temp namespace unavailable') { throw 'expected allocator refusal was not reported' }
if (Test-Path -LiteralPath 'spawned.marker') { throw 'pytest spawned after allocation failure' }
""",
    )
    assert result.returncode == 0, result.stderr
