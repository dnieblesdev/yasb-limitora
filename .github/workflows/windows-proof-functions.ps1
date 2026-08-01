$script:NativeKnownTests = @{
  "test_native_helper_adapter_ipc_and_complete_job_tree_cleanup" = "helper-tree-cleanup"
  "test_sentinel_scan_failure_diagnostics_are_redacted" = "sentinel-scan-redaction"
  "test_nested_job_is_explicit_safe_failure_without_authorization" = "nested-job-fail-closed"
  "test_supervisor_setup_failure_is_safe_and_does_not_run_runner" = "supervisor-setup-fail-closed"
}

function Scan-Candidates($candidates) {
  $unsafeClasses = @(); $failedTests = @(); $scanFailed = $false
  foreach ($candidate in $candidates) {
    if (-not (Test-Path $candidate.Path)) { continue }
    try {
      $content = [IO.File]::ReadAllText((Resolve-Path $candidate.Path))
      if ($candidate.Label -eq "junit") {
        try {
          $report = [xml]$content
          foreach ($suite in @($report.testsuites.testsuite)) {
            foreach ($testcase in @($suite.testcase)) {
              if ($null -ne $testcase.failure -or $null -ne $testcase.error) {
                $name = [string]$testcase.name
                $failedTests += if ($script:NativeKnownTests.ContainsKey($name)) { $script:NativeKnownTests[$name] } else { "unknown" }
              }
            }
          }
        } catch { $failedTests += "unknown" }
      }
      if ($content.Contains("native-redaction-sentinel")) {
        $unsafeClasses += $candidate.Label
        Remove-Item -Force -ErrorAction Stop $candidate.Path
      }
    } catch {
      $unsafeClasses += $candidate.Label; $scanFailed = $true
    }
  }
  $unsafeClasses = @($unsafeClasses | Select-Object -Unique)
  $failedTests = @($failedTests | Select-Object -Unique)
  if ($unsafeClasses.Count -gt 0 -and $failedTests.Count -eq 0) { $failedTests = @("unknown") }
  [PSCustomObject]@{ UnsafeClasses = $unsafeClasses; FailedTests = $failedTests; ScanFailed = $scanFailed }
}

function Assert-SafeScan($scan, $exitClass, $phase, $checkpoint) {
  $allowed = @("raw-log", "junit", "evidence")
  $invalid = @($scan.UnsafeClasses | Where-Object { $_ -notin $allowed })
  $classes = $scan.UnsafeClasses -join ","
  $tests = $scan.FailedTests -join ","
  if ($invalid.Count -gt 0) { throw "$phase safety classification invalid; candidates=$classes; failed_tests=$tests; pytest_exit=$exitClass; checkpoint=$checkpoint" }
  if ($scan.ScanFailed) { throw "$phase safety cleanup failed; candidates=$classes; failed_tests=$tests; pytest_exit=$exitClass; checkpoint=$checkpoint" }
  if ($scan.UnsafeClasses.Count -gt 0) { throw "$phase safety failure; candidates=$classes; failed_tests=$tests; pytest_exit=$exitClass; checkpoint=$checkpoint" }
}

function Read-NativeCheckpoint($phase, $exitClass) {
  $checkpoint = "unknown"; $classifierFailed = $false
  try {
    $result = @(& python tests/test_windows_native_proof.py --classify-checkpoint $env:YASB_NATIVE_CHECKPOINT_PATH 2>$null)
    if ($LASTEXITCODE -ne 0 -or $result.Count -ne 1 -or $result[0] -notin @("1", "2", "3", "4", "5", "6", "7", "8", "9", "unknown")) { $classifierFailed = $true }
    else { $checkpoint = [string]$result[0] }
  } catch { $classifierFailed = $true }
  try {
    if (Test-Path -LiteralPath $env:YASB_NATIVE_CHECKPOINT_PATH) { Remove-Item -LiteralPath $env:YASB_NATIVE_CHECKPOINT_PATH -Force -ErrorAction Stop }
  } catch {
    throw "$phase checkpoint unavailable; checkpoint=$checkpoint; pytest_exit=$exitClass"
  }
  if ($classifierFailed) { throw "$phase checkpoint unavailable; checkpoint=$checkpoint; pytest_exit=$exitClass" }
  return $checkpoint
}

function Emit-SafeLog($path, $exitClass, $phase) {
  if (Test-Path $path) {
    try { Get-Content $path -ErrorAction Stop; Remove-Item -Force -ErrorAction Stop $path }
    catch { throw "$phase diagnostics unavailable; pytest_exit=$exitClass" }
  }
}

function Invoke-NativePytestWmi {
  param(
    [ValidateSet("selected", "full")][string]$Mode,
    [string]$Phase,
    [ValidateSet("native-proof.raw.log", "full-suite.raw.log")][string]$RawLogName
  )
  $workspace = (Get-Location).Path
  $pythonExe = Join-Path $env:pythonLocation "python.exe"
  if (-not [IO.Path]::IsPathRooted($pythonExe) -or -not (Test-Path -LiteralPath $pythonExe)) {
    throw "$Phase WMI proof unavailable"
  }
  $id = [guid]::NewGuid().ToString("N")
  $prefix = "YasbLimitoraNativeProof-$id"
  $launcherPath = Join-Path $workspace "$prefix.ps1"
  $exitPath = Join-Path $workspace "$prefix.exit"
  $exitTempPath = "$exitPath.tmp"
  $rawLogPath = Join-Path $workspace $RawLogName
  $privateRawPath = Join-Path $workspace "$prefix.raw.log"
  $pytestArguments = if ($Mode -eq "selected") {
    @("-m", "pytest", "-q", "--strict-markers", "tests/test_windows_native_proof.py", "--junitxml=native-proof.xml")
  } else {
    @("-m", "pytest", "-q", "--strict-markers", "tests")
  }
  $argumentLines = ($pytestArguments | ForEach-Object { "    `"$_`"" }) -join "`r`n"
  $launcher = @"
`$ErrorActionPreference = "Stop"
`$pythonExe = "$pythonExe"
`$workspace = (Get-Location).Path
`$rawLog = Join-Path `$workspace "$prefix.raw.log"
`$exitPath = Join-Path `$workspace "$prefix.exit"
`$env:YASB_NATIVE_EVIDENCE_PATH = "native-proof.json"
`$env:YASB_NATIVE_CHECKPOINT_PATH = "native-proof.checkpoint"
`$env:PYTHONUTF8 = "1"
`$pytestArguments = @(
$argumentLines
)
`$exitCode = 1
try {
  Set-Location -LiteralPath `$workspace
  & `$pythonExe @pytestArguments *> `$rawLog
  `$exitCode = `$LASTEXITCODE
} catch {
  `$exitCode = 1
}
try {
  `$tempExit = "`$exitPath.tmp"
  [IO.File]::WriteAllText(`$tempExit, "`$exitCode`r`n", [Text.Encoding]::ASCII)
  [IO.File]::Move(`$tempExit, `$exitPath)
} catch {
  exit 1
}
exit `$exitCode
"@
  $wmiPid = $null
  $result = $null
  $cleanupFailed = $false
  try {
    [IO.File]::WriteAllText($launcherPath, $launcher, [Text.UTF8Encoding]::new($false))
    $powerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $commandLine = "`"$powerShell`" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$launcherPath`""
    $created = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $commandLine; CurrentDirectory = $workspace } -ErrorAction Stop
    if ([int]$created.ReturnValue -ne 0 -or [int]$created.ProcessId -le 0) { throw "$Phase WMI process creation failed" }
    $wmiPid = [int]$created.ProcessId
    $deadline = [DateTime]::UtcNow.AddSeconds(180)
    while (-not (Test-Path -LiteralPath $exitPath)) {
      if ([DateTime]::UtcNow -ge $deadline) { throw "$Phase WMI proof timed out" }
      Start-Sleep -Milliseconds 250
    }
    $status = (Get-Content -LiteralPath $exitPath -Raw -ErrorAction Stop)
    if ($status -notmatch "^(0|[1-9][0-9]{0,2})`r?`n$") { throw "$Phase WMI exit status invalid" }
    $result = [int]$status.Trim()
    $processDeadline = [DateTime]::UtcNow.AddSeconds(10)
    while (Get-Process -Id $wmiPid -ErrorAction SilentlyContinue) {
      if ([DateTime]::UtcNow -ge $processDeadline) { throw "$Phase WMI process exit timed out" }
      Start-Sleep -Milliseconds 100
    }
    $wmiPid = $null
  } catch {
    throw "$Phase WMI proof unavailable"
  } finally {
    if ($wmiPid) {
      try {
        if (Get-Process -Id $wmiPid -ErrorAction SilentlyContinue) {
          & (Join-Path $env:SystemRoot "System32\taskkill.exe") /PID $wmiPid /T /F *> $null
          if ($LASTEXITCODE -ne 0) { throw "$Phase WMI process-tree cleanup failed" }
        }
      } catch { $cleanupFailed = $true }
    }
    if (Test-Path -LiteralPath $privateRawPath) {
      try { Move-Item -LiteralPath $privateRawPath -Destination $rawLogPath -Force -ErrorAction Stop } catch { $cleanupFailed = $true }
    }
    foreach ($path in @($launcherPath, $exitPath, $exitTempPath, $privateRawPath)) {
      if (Test-Path -LiteralPath $path) {
        try { Remove-Item -LiteralPath $path -Force -ErrorAction Stop } catch { $cleanupFailed = $true }
      }
    }
    if ($cleanupFailed) { throw "$Phase WMI proof cleanup failed" }
  }
  return $result
}
