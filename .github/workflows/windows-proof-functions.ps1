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
