$script:R10Python = Join-Path $env:pythonLocation "python.exe"

function Assert-R10Artifact($path, $expectedName, $expectedSha256) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "R10 artifact unavailable" }
  if ([IO.Path]::GetFileName($path) -cne $expectedName) { throw "R10 artifact filename mismatch" }
  $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -cne $expectedSha256) { throw "R10 artifact hash mismatch" }
}

function Assert-R10Pe($path) {
  $bytes = [IO.File]::ReadAllBytes($path)
  if ($bytes.Length -lt 64 -or $bytes[0] -ne 0x4d -or $bytes[1] -ne 0x5a) { throw "R10 fixture is not a PE" }
  $offset = [BitConverter]::ToInt32($bytes, 60)
  if ($offset -lt 64 -or $offset + 4 -gt $bytes.Length -or [Text.Encoding]::ASCII.GetString($bytes, $offset, 4) -cne "PE`0`0") { throw "R10 fixture is not a PE" }
}

function Resolve-R10Launcher {
  $scripts = Join-Path $env:pythonLocation "Scripts"
  $candidates = @(Get-ChildItem -LiteralPath $scripts -Filter "yasb-limitora*.exe" -File -ErrorAction SilentlyContinue)
  if ($candidates.Count -ne 1 -or $candidates[0].Name -cne "yasb-limitora.exe" -or $candidates[0].FullName.Contains(" ")) { throw "R10 launcher is ambiguous or contains spaces" }
  return $candidates[0]
}

function ConvertTo-R10ProcessArgument([string]$argument) {
  if ($argument -notmatch '[\s"]') { return $argument }
  return '"' + (($argument -replace '(\\*)"', '$1$1\"') -replace '(\\+)$', '$1$1') + '"'
}

function Get-R10JUnitDiagnostic([string[]]$Arguments) {
  try {
    $trace = $env:R10_JUNIT_DIAGNOSTIC_STAGE -eq "1"; $stage = "args"; $withheld = { param($s) if ($trace) { "diagnostics withheld; stage=$s" } else { "diagnostics withheld" } }
    $known = @("r10-admission.xml", "r10-yasb-experience.xml"); $paths = @($Arguments | % { $m = [regex]::Match($_, '^--junitxml=(?<path>[^\\/:]+\.xml)$'); if ($m.Success) { $m.Groups.path.Value } }); if ($paths.Count -ne 1 -or $paths[0] -notin $known -or -not (Test-Path -LiteralPath $paths[0] -PathType Leaf)) { return & $withheld $stage }; $stage = "xml"
    $r = [xml](Get-Content -LiteralPath $paths[0] -Raw -ErrorAction Stop); $stage = "candidate"; $c = @(@($r.testsuites.testsuite) + @($r.testsuite) | % { $_.testcase } | ? { $null -ne $_.failure -or $null -ne $_.error } | select -First 1); if ($null -eq $c) { return & $withheld $stage }; $stage = "node"; $n = if ($null -ne $c.failure) { $c.failure } else { $c.error }; $raw = "$($n.message) $($n.InnerText)"; $stage = "match"; $lm = [regex]::Match($raw, '(?i)(?:(?:[A-Za-z]:[\\/]|/|(?:[^\\/:<>"'']+[\\/])+)[^:\r\n]+:(?<line>[0-9]{1,6})(?::[0-9]+)?|File\s+["''](?:[A-Za-z]:[\\/]|/)[^"'']+["''],\s+line\s+(?<line>[0-9]{1,6})(?:,\s+in\b|\b))'); if (!$lm.Success) { return & $withheld $stage }
    $stage = "sanitize"; $s = { param($v) $v = [regex]::Replace([string]$v, '(?i)\b(?:password|passwd|credential|api[ _-]?key|authorization|cookie|token|secret)\b[ \t]*[:=][ \t]*(?:"[^"\r\n]*"|''[^''\r\n]*''|[^,;\r\n]*)', '[REDACTED]'); [regex]::Replace([regex]::Replace($v, '(?i)[A-Za-z]:[\\/][^\r\n"''<>;,]*(?=["'']?(?::[0-9]{1,6}(?::[0-9]+)?(?:\b|$)|[;,])|["''],\s+line\s+[0-9]{1,6})|(?<![\w])/(?:[^/\r\n"''<>;,]+/)+[^\r\n"''<>;,]*(?=["'']?(?::[0-9]{1,6}(?::[0-9]+)?(?:\b|$)|[;,])|["''],\s+line\s+[0-9]{1,6})', '[PATH]'), '\s+', ' ').Trim() }; $stage = "assemble"; $d = "R10 diagnostic: test=$(&$s $c.name); line=$($lm.Groups.line.Value); message=$(&$s $raw)"; if ($d.Length -gt 240) { $d = $d.Substring(0, 240) }; return $d
  } catch { return & $withheld $stage }
}

function Invoke-R10CheckedPython {
  param([string]$Label, [string[]]$Arguments, [int]$TimeoutSeconds = 180)
  $root = Join-Path $env:RUNNER_TEMP "r10-checked-python"
  New-Item -ItemType Directory -Force $root | Out-Null
  $id = [guid]::NewGuid().ToString("N")
  $stdout = Join-Path $root "$id.out"
  $stderr = Join-Path $root "$id.err"
  $process = $null
  try {
    $process = Start-Process -FilePath $script:R10Python -ArgumentList (($Arguments | ForEach-Object { ConvertTo-R10ProcessArgument $_ }) -join " ") -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
      $tree = @(Get-CimInstance Win32_Process -Property ProcessId,ParentProcessId -ErrorAction Stop)
      if ($tree.Count -gt 4096 -or @($tree | Select-Object -ExpandProperty ProcessId -Unique).Count -ne $tree.Count -or @($tree | Where-Object { $null -eq $_.ProcessId -or $null -eq $_.ParentProcessId }).Count -gt 0 -or @($tree | Where-Object ProcessId -eq $process.Id).Count -ne 1) { throw "$Label timed out; process-tree metadata unavailable; diagnostics withheld" }
      $pids = [System.Collections.Generic.HashSet[int]]::new(); $pending = [System.Collections.Generic.Queue[int]]::new(); $pending.Enqueue([int]$process.Id)
      while ($pending.Count) { $parent = $pending.Dequeue(); foreach ($node in @($tree | Where-Object ParentProcessId -eq $parent)) { if ([int]$node.ProcessId -eq $process.Id -or -not $pids.Add([int]$node.ProcessId)) { throw "$Label timed out; process-tree metadata ambiguous; diagnostics withheld" }; $pending.Enqueue([int]$node.ProcessId) } }
      & (Join-Path $env:SystemRoot "System32\taskkill.exe") /PID $process.Id /T /F *> $null
      if ($LASTEXITCODE -ne 0 -or -not $process.WaitForExit(5000)) { throw "$Label timed out; process-tree termination unconfirmed; diagnostics withheld" }
      $remaining = @(foreach ($candidatePid in @($process.Id) + @($pids)) { $matches = @(Get-CimInstance Win32_Process -Filter "ProcessId = $candidatePid" -ErrorAction Stop); if ($matches.Count -gt 1) { throw "$Label timed out; process verification ambiguous; diagnostics withheld" }; if ($matches.Count -eq 1) { $candidatePid } })
      if ($remaining.Count) { throw "$Label timed out; process-tree termination unconfirmed; diagnostics withheld" }
      throw "$Label timed out; diagnostics withheld"
    }
    if ($process.ExitCode -ne 0) { throw "$Label failed; exit=$($process.ExitCode); $(Get-R10JUnitDiagnostic $Arguments)" }
    return $process.ExitCode
  } catch {
    if ($_.Exception.Message -like "$Label failed*" -or $_.Exception.Message -like "$Label timed out*") { throw }
    throw "$Label unavailable; diagnostics withheld"
  } finally {
    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
  }
}

function Assert-R10WinRtImports {
  $script = 'import importlib,importlib.metadata as m,os,sys; root=os.path.realpath(sys.prefix).lower(); expected={"PyQt6.QtCore":("PyQt6","6.10.2"),"pydantic":("pydantic","2.13.4"),"pydantic_core":("pydantic-core","2.46.4"),"yaml":("PyYAML","6.0.3"),"_yaml":("PyYAML","6.0.3"),"win32api":("pywin32","312"),"pywintypes":("pywin32","312"),"winrt.system":("winrt-runtime","3.2.1"),"winrt.windows.data.xml.dom":("winrt-windows-data-xml-dom","3.2.1"),"winrt.windows.ui.notifications":("winrt-windows-ui-notifications","3.2.1"),"winrt.windows.management.deployment":("winrt-windows-management-deployment","3.2.1")}; [(lambda x: x.__file__ and os.path.realpath(x.__file__).lower().startswith(root+os.sep) and m.version(expected[n][0])==expected[n][1] or (_ for _ in ()).throw(ImportError(n)))(importlib.import_module(n)) for n in expected]'
  Invoke-R10CheckedPython "R10 WinRT import smoke" @("-c", $script)
}

function Assert-R10PytestResult($junitPath, $exitCode) {
  if ($exitCode -ne 0 -or -not (Test-Path -LiteralPath $junitPath)) { throw "R10 admission failed; diagnostics withheld" }
  try { $report = [xml](Get-Content -LiteralPath $junitPath -Raw) } catch { throw "R10 admission report unavailable" }
  $suites = @($report.testsuites.testsuite)
  if ($suites.Count -eq 0 -and $report.testsuite) { $suites = @($report.testsuite) }
  $tests = 0; $skipped = 0; $failures = 0; $errors = 0
  try { foreach ($suite in $suites) { $tests += [int]$suite.tests; $skipped += [int]$suite.skipped; $failures += [int]$suite.failures; $errors += [int]$suite.errors } } catch { throw "R10 admission report counts invalid" }
  if ($suites.Count -eq 0 -or $tests -lt 1 -or $skipped -ne 0 -or $failures -ne 0 -or $errors -ne 0) { throw "R10 admission was skipped or failed" }
}

function Assert-R10Shape($value, [string[]]$fields, [string]$label) {
  if ($null -eq $value) { throw "R10 $label evidence missing" }
  $actual = @($value.PSObject.Properties.Name)
  if ($actual.Count -ne $fields.Count -or @($fields | Where-Object { $_ -cnotin $actual }).Count -gt 0 -or @($actual | Where-Object { $_ -cnotin $fields }).Count -gt 0) { throw "R10 $label evidence schema mismatch" }
}

function Assert-R10ExperienceEvidence($path) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "R10 native experience evidence unavailable" }
  try { $evidence = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json } catch { throw "R10 native experience evidence invalid" }
  Assert-R10Shape $evidence @("native", "lifecycle", "identity", "expected", "observed", "launcher_streams", "launcher_paths", "sanitization", "r11_handoff") "root"
  Assert-R10Shape $evidence.identity @("yasb_version", "yasb_commit", "custom_module_sha256", "python", "architecture", "qt_platform", "launcher_name", "launcher_sha256_before", "launcher_sha256_after", "shadow_launcher_sha256") "identity"
  Assert-R10Shape $evidence.expected @("primary_label", "alternate_label", "tooltip", "alternate_tooltip", "malformed_label", "malformed_alternate_label", "malformed_tooltip", "malformed_visible", "valid_toggle", "alternate_toggle", "malformed_toggle", "final_toggle", "css_class", "configured_refresh_ms") "expected"
   Assert-R10Shape $evidence.observed @("valid", "alternate", "malformed", "final", "css", "cleanup", "qt_platform", "timer_interval_test_ms", "timer_refresh_count", "valid_to_malformed_to_valid") "observed"
  foreach ($phase in @("valid", "alternate")) { Assert-R10Shape $evidence.observed.$phase @("primary_label", "alternate_label", "tooltip", "visible", "toggle") $phase }
  Assert-R10Shape $evidence.observed.malformed @("primary_label", "alternate_label", "tooltip", "visible", "fallback", "toggle") "malformed"
  Assert-R10Shape $evidence.observed.final @("primary_label", "alternate_label", "tooltip", "visible", "toggle", "path_restored", "final_real_qtimer_refresh") "final"
  foreach ($toggle in @("valid_toggle", "alternate_toggle", "malformed_toggle", "final_toggle")) { Assert-R10Shape $evidence.expected.$toggle @("primary_visible", "alternate_visible") "expected.$toggle" }
  foreach ($phase in @("valid", "alternate", "malformed", "final")) { Assert-R10Shape $evidence.observed.$phase.toggle @("primary_visible", "alternate_visible") "$phase.toggle" }
   Assert-R10Shape $evidence.observed.css @("processor", "processed", "stylesheet_applied", "classes") "css"
   Assert-R10Shape $evidence.observed.css.classes @("widget", "primary", "alternate") "css.classes"
   Assert-R10Shape $evidence.observed.cleanup @("timer_inactive", "worker_stopped", "worker_threads_terminated", "worker_released", "worker_deleted", "subprocesses_terminated", "widget_closed", "widget_deleted") "cleanup"
  Assert-R10Shape $evidence.launcher_paths @("installed", "shadow", "path_restored") "launcher_paths"
  Assert-R10Shape $evidence.sanitization @("secret_like_output", "raw_streams_persisted", "paths_redacted", "status") "sanitization"
  Assert-R10Shape $evidence.r11_handoff @("status", "next", "excluded") "r11_handoff"
  if ($evidence.native -ne $true -or $evidence.identity.qt_platform -cne "windows" -or $evidence.observed.qt_platform -cne "windows") { throw "R10 native Qt platform evidence invalid" }
  if ($evidence.expected.primary_label -cne "Quota 80% remaining; state=available; freshness=fresh" -or $evidence.expected.alternate_label -cne "Quota account / day: 80% remaining; state=available; freshness=fresh" -or $evidence.expected.tooltip -cne "State: available`nFreshness: fresh`nQuota: 80% remaining" -or $evidence.expected.alternate_tooltip -cne $evidence.expected.tooltip -or $evidence.expected.malformed_label -cne "{data[providers][0][compact_text]}" -or $evidence.expected.malformed_alternate_label -cne "{data[providers][0][alternate_text]}" -or $evidence.expected.malformed_tooltip -cne "None" -or $evidence.expected.malformed_visible -ne $false -or $evidence.expected.valid_toggle.primary_visible -ne $true -or $evidence.expected.valid_toggle.alternate_visible -ne $false -or $evidence.expected.alternate_toggle.primary_visible -ne $false -or $evidence.expected.alternate_toggle.alternate_visible -ne $true -or $evidence.expected.malformed_toggle.primary_visible -ne $false -or $evidence.expected.malformed_toggle.alternate_visible -ne $false -or $evidence.expected.final_toggle.primary_visible -ne $true -or $evidence.expected.final_toggle.alternate_visible -ne $false -or $evidence.expected.css_class -cne "widget custom-widget limitora-r9" -or [int]$evidence.expected.configured_refresh_ms -ne 120000) { throw "R10 expected experience evidence mismatch" }
  if ($evidence.observed.valid.primary_label -cne $evidence.expected.primary_label -or $evidence.observed.valid.alternate_label -cne $evidence.expected.alternate_label -or $evidence.observed.valid.tooltip -cne $evidence.expected.tooltip -or $evidence.observed.valid.visible -ne $true -or $evidence.observed.valid.toggle.primary_visible -ne $evidence.expected.valid_toggle.primary_visible -or $evidence.observed.valid.toggle.alternate_visible -ne $evidence.expected.valid_toggle.alternate_visible) { throw "R10 valid observation mismatch" }
  if ($evidence.observed.alternate.primary_label -cne $evidence.expected.primary_label -or $evidence.observed.alternate.alternate_label -cne $evidence.expected.alternate_label -or $evidence.observed.alternate.tooltip -cne $evidence.expected.alternate_tooltip -or $evidence.observed.alternate.visible -ne $true -or $evidence.observed.alternate.toggle.primary_visible -ne $evidence.expected.alternate_toggle.primary_visible -or $evidence.observed.alternate.toggle.alternate_visible -ne $evidence.expected.alternate_toggle.alternate_visible) { throw "R10 alternate observation mismatch" }
  if ($evidence.observed.malformed.primary_label -cne $evidence.expected.malformed_label -or $evidence.observed.malformed.alternate_label -cne $evidence.expected.malformed_alternate_label -or $evidence.observed.malformed.tooltip -cne $evidence.expected.malformed_tooltip -or $evidence.observed.malformed.visible -ne $evidence.expected.malformed_visible -or $evidence.observed.malformed.fallback -cne "raw_template_labels_and_literal_None" -or $evidence.observed.malformed.toggle.primary_visible -ne $evidence.expected.malformed_toggle.primary_visible -or $evidence.observed.malformed.toggle.alternate_visible -ne $evidence.expected.malformed_toggle.alternate_visible) { throw "R10 malformed observation mismatch" }
  if ($evidence.observed.final.primary_label -cne $evidence.expected.primary_label -or $evidence.observed.final.alternate_label -cne $evidence.expected.alternate_label -or $evidence.observed.final.tooltip -cne $evidence.expected.tooltip -or $evidence.observed.final.visible -ne $true -or $evidence.observed.final.toggle.primary_visible -ne $evidence.expected.final_toggle.primary_visible -or $evidence.observed.final.toggle.alternate_visible -ne $evidence.expected.final_toggle.alternate_visible -or $evidence.observed.final.path_restored -ne $true -or $evidence.observed.final.final_real_qtimer_refresh -ne $true) { throw "R10 final recovery observation mismatch" }
  if ($evidence.observed.css.processor -cne "core.utils.css_processor.CSSProcessor" -or $evidence.observed.css.processed -ne $true -or $evidence.observed.css.stylesheet_applied -ne $true -or $evidence.observed.css.classes.widget -cne $evidence.expected.css_class -or $evidence.observed.css.classes.primary -cne "label" -or $evidence.observed.css.classes.alternate -cne "label alt") { throw "R10 CSS processing evidence mismatch" }
   if ([int]$evidence.observed.timer_interval_test_ms -ne 50 -or [int]$evidence.observed.timer_refresh_count -lt 2 -or $evidence.observed.valid_to_malformed_to_valid -ne $true) { throw "R10 refresh evidence incomplete" }
     if ($evidence.observed.cleanup.timer_inactive -ne $true -or $evidence.observed.cleanup.worker_stopped -ne $true -or $evidence.observed.cleanup.worker_threads_terminated -ne $true -or $evidence.observed.cleanup.worker_released -ne $true -or $evidence.observed.cleanup.worker_deleted -ne $true -or $evidence.observed.cleanup.subprocesses_terminated -ne $true -or $evidence.observed.cleanup.widget_closed -ne $true -or $evidence.observed.cleanup.widget_deleted -ne $true) { throw "R10 CustomWidget cleanup evidence incomplete" }
   if (($evidence.lifecycle -join ",") -cne "constructed,valid,alternate,malformed,restored_valid,cleaned") { throw "R10 lifecycle evidence mismatch" }
  if ($evidence.launcher_paths.installed -cne "<sys.prefix>/Scripts/yasb-limitora.exe" -or $evidence.launcher_paths.shadow -cne "<temp>/r10-yasb-shadow/yasb-limitora.exe" -or $evidence.launcher_paths.path_restored -ne $true) { throw "R10 launcher path evidence mismatch" }
  if ($evidence.identity.launcher_name -cne "yasb-limitora.exe" -or $evidence.identity.launcher_sha256_before -notmatch "^[0-9a-f]{64}$" -or $evidence.identity.launcher_sha256_after -cne $evidence.identity.launcher_sha256_before -or $evidence.identity.shadow_launcher_sha256 -notmatch "^[0-9a-f]{64}$") { throw "R10 launcher hash evidence mismatch" }
  $roles = @("installed_before", "shadow_valid", "shadow_malformed", "installed_after"); $streams = @($evidence.launcher_streams)
  if ($streams.Count -ne $roles.Count) { throw "R10 launcher stream evidence incomplete" }
  for ($index = 0; $index -lt $roles.Count; $index++) { Assert-R10Shape $streams[$index] @("role", "launcher_name", "launcher_path", "exit_code", "stdout_bytes", "stderr_bytes", "stderr_empty", "stdout_sha256") "launcher_streams[$index]"; if ($streams[$index].role -cne $roles[$index] -or $streams[$index].launcher_name -cne "yasb-limitora.exe" -or $streams[$index].exit_code -ne 0 -or [int]$streams[$index].stdout_bytes -lt 1 -or [int]$streams[$index].stderr_bytes -ne 0 -or $streams[$index].stderr_empty -ne $true -or $streams[$index].stdout_sha256 -notmatch "^[0-9a-f]{64}$") { throw "R10 launcher stream evidence mismatch" } }
  if ([int]$streams[2].stdout_bytes -ne 1 -or $streams[0].launcher_path -cne $evidence.launcher_paths.installed -or $streams[1].launcher_path -cne $evidence.launcher_paths.shadow -or $streams[2].launcher_path -cne $evidence.launcher_paths.shadow -or $streams[3].launcher_path -cne $evidence.launcher_paths.installed) { throw "R10 launcher path stream mismatch" }
  if ($evidence.sanitization.secret_like_output -ne $false -or $evidence.sanitization.raw_streams_persisted -ne $false -or $evidence.sanitization.paths_redacted -ne $true -or $evidence.sanitization.status -cne "pass") { throw "R10 native experience sanitization failed" }
  $content = [IO.File]::ReadAllText((Resolve-Path $path))
  if ($content -match "(?i)password|api[_-]?key|authorization|cookie|native-redaction-sentinel|[A-Za-z]:\\\\|/home/|/tmp/|RUNNER_TEMP") { throw "R10 native experience evidence contains unsafe output" }
}

function Invoke-R10WithPath($action) {
  $savedPath = $env:Path
  try { & $action }
  finally {
    $env:Path = $savedPath
    if ($env:Path -ne $savedPath) { throw "PATH restoration failed" }
  }
}

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
    @("-m", "pytest", "-q", "--strict-markers", "tests/test_windows_native_proof.py", "-k", "not native_yasb_customwidget_lifecycle_and_recovery", "--junitxml=native-proof.xml")
  } else {
    @("-m", "pytest", "-q", "--strict-markers", "tests", "-k", "not native_yasb_customwidget_lifecycle_and_recovery", "--junitxml=native-proof.xml")
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
