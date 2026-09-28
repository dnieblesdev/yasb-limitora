<#
.SYNOPSIS
    Guest watcher - resident scenario executor for S11b lifecycle.
.DESCRIPTION
    Runs in the interactive session, started once and preserved by the
    checkpoint's saved RAM. Each cycle it resolves the S11BEVIDENCE volume,
    waits for scenario.json, validates it, executes steps through the
    existing harnesses, answers only declared dialogs, writes done.json,
    and shuts the guest down cleanly on success.
    Fail-closed: any unexpected condition stops the cycle without shutting
    the guest down, so the parent can inspect.
.NOTES
    Windows PowerShell 5.1 compatible. No Path.GetRelativePath.
    Get-FileHash is available in the guest context.
    Resident-wait semantics: the evidence-volume wait is unbounded by design, because an absolute
    deadline computed here would be frozen in a checkpoint's saved RAM and invalidated by the next
    revert plus Hyper-V Time Synchronization on resume. The host owns the per-cycle budget.
    Dialog matching covers a dialog's caption plus all of its child-window texts, so a declared
    fragment of the message body matches an Inno message box whose caption is only the setup title.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

#region P/Invoke and type declarations

if (-not ('S11B.WatcherNative' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Text;
using System.Runtime.InteropServices;

namespace S11B {
    public static class WatcherNative {
        public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

        [DllImport("user32.dll", SetLastError = true)]
        public static extern bool EnumWindows(EnumWindowsProc enumProc, IntPtr lParam);

        [DllImport("user32.dll", SetLastError = true)]
        public static extern bool EnumChildWindows(IntPtr hWndParent, EnumWindowsProc enumProc, IntPtr lParam);

        [DllImport("user32.dll", SetLastError = true)]
        public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

        [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        public static extern int GetClassName(IntPtr hWnd, StringBuilder className, int maxCount);

        [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int maxCount);

        [DllImport("user32.dll")]
        public static extern bool PostMessage(IntPtr hWnd, uint Msg, int wParam, int lParam);

        public const uint WM_COMMAND = 0x0111;

        public static string CollectDialogText(IntPtr hWnd) {
            // A dialog's caption is its window text, but the message body lives in child windows
            // (Static controls), so match against the combined text of the dialog and every
            // descendant. Without this, a declared answer that names the message body can never
            // match an Inno message box whose caption is only the setup or uninstall title.
            var combined = new StringBuilder(8192);
            var captionBuffer = new StringBuilder(4096);
            WatcherNative.GetWindowText(hWnd, captionBuffer, 4096);
            if (captionBuffer.Length > 0) combined.Append(captionBuffer.ToString());
            WatcherNative.EnumChildWindows(hWnd, (child, lp) => {
                var childBuffer = new StringBuilder(2048);
                WatcherNative.GetWindowText(child, childBuffer, 2048);
                if (childBuffer.Length > 0) {
                    if (combined.Length > 0) combined.Append('\n');
                    combined.Append(childBuffer.ToString());
                }
                return true;
            }, IntPtr.Zero);
            return combined.ToString();
        }
    }

    public class DialogAnswerSpec {
        public string Match;
        public int ButtonId;
    }

    public class DialogScanResult {
        public IntPtr MatchedHwnd = IntPtr.Zero;
        public int MatchedButtonId = 0;
        public IntPtr UndeclaredHwnd = IntPtr.Zero;
        public string UndeclaredText = "";
        public HashSet<int> DescendantPids;
        public List<DialogAnswerSpec> Answers;

        public bool EnumCallback(IntPtr hWnd, IntPtr lParam) {
            var classNameBuffer = new StringBuilder(256);
            WatcherNative.GetClassName(hWnd, classNameBuffer, 256);
            if (classNameBuffer.ToString() != "#32770") return true;

            uint pid;
            WatcherNative.GetWindowThreadProcessId(hWnd, out pid);
            var inStepTree = (DescendantPids != null && DescendantPids.Contains((int)pid));

            var text = WatcherNative.CollectDialogText(hWnd);
            if (string.IsNullOrEmpty(text)) return true;

            if (Answers != null) {
                foreach (var answer in Answers) {
                    if (text.IndexOf(answer.Match, StringComparison.OrdinalIgnoreCase) >= 0) {
                        // A declared answer is the operator's recorded decision, so it is matched by text
                        // over any top-level dialog, not only over the step's process tree: an Inno
                        // uninstaller re-executes itself from a temporary copy, so its windows are not
                        // reachable by the step's descendant walk. The operator would answer exactly the
                        // dialog on screen.
                        MatchedHwnd = hWnd;
                        MatchedButtonId = answer.ButtonId;
                        return false;
                    }
                }
            }

            // Undeclared-dialog detection stays limited to the step's process tree so that unrelated
            // shell dialogs never fail a cycle. A dialog from a relaunched step process that matches
            // nothing declared is still caught by the per-step timeout (fail-closed, but slower).
            if (!inStepTree) return true;
            UndeclaredHwnd = hWnd;
            UndeclaredText = text;
            return true;
        }
    }
}
'@
}

#endregion

#region Constants

$script:EvidenceLabel = 'S11BEVIDENCE'
$script:ScenarioFileName = 'scenario.json'
$script:DoneFileName = 'done.json'
$script:LogFileName = 'watcher.log'
$script:SchemaVersion = 'gentle-ai.yasb-limitora.s11b-scenario/v1'
$script:DoneSchemaVersion = 'gentle-ai.yasb-limitora.s11b-done/v1'
$script:ScenarioWaitTimeoutSeconds = 300
$script:DialogPollIntervalMs = 500
$script:DialogTimeoutSeconds = 120
$script:WaitStepMaxMs = 300000
$script:MaxLogBytes = 1048576
$script:PhaseIdPattern = '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$'

#endregion

#region Logging

function Get-ObjectProperty {
    # StrictMode-safe optional read for both ConvertFrom-Json objects and the OrderedDictionary
    # results returned by step functions. OrderedDictionary keys are not PSObject.Properties, so
    # checking only PSObject.Properties would hide a non-zero exitCode and defeat fail-closed.
    param($Object, [string] $Name)
    if ($null -eq $Object) { return $null }
    if ($Object -is [System.Collections.IDictionary] -and $Object.Contains($Name)) {
        return $Object[$Name]
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Get-SelfSha256 {
    # SHA-256 of the script file this process was started from, as the guest currently reads it.
    # A checkpoint's saved RAM can carry a stale CD-ROM cache, so a guest may execute an older
    # watcher build than the one on the host; logging this hash makes the running build explicit in
    # every scenario's watcher.log, and the expected-watcher.sha256 stamp turns a stale build into an
    # immediate fail-closed instead of a silently wrong run.
    $path = $PSCommandPath
    if ([string]::IsNullOrWhiteSpace($path)) { return $null }
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    try {
        if (Get-Command Get-FileHash -ErrorAction SilentlyContinue) {
            return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    } catch { }
    try {
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            $fs = [IO.File]::OpenRead($path)
            try { return ([BitConverter]::ToString($sha.ComputeHash($fs))).Replace('-', '').ToLowerInvariant() } finally { $fs.Dispose() }
        } finally { $sha.Dispose() }
    } catch { return $null }
}

function Write-WatcherLog {
    param([string] $Message, [string] $Level = 'INFO')
    $timestamp = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
    $line = "$timestamp [$Level] $Message"
    # Write-Host, not Write-Output: a log line must never enter the caller's output stream, because
    # several callers assign a function's return value (for example
    # `$evidenceRoot = Wait-ForEvidenceVolume`); Write-Output there would swallow every log line and
    # turn the return value into an array of strings plus the real result.
    Write-Host $line
    if ($script:LogPath) {
        try {
            $existing = ''
            if (Test-Path -LiteralPath $script:LogPath) {
                $existing = [IO.File]::ReadAllText($script:LogPath, [Text.Encoding]::UTF8)
            }
            $newContent = $existing + $line + "`n"
            if ([Text.Encoding]::UTF8.GetByteCount($newContent) -gt $script:MaxLogBytes) {
                $truncateAt = [math]::Max(0, $newContent.Length - 4096)
                $newContent = "... (truncated) `n" + $newContent.Substring($truncateAt)
            }
            [IO.File]::WriteAllText($script:LogPath, $newContent, [Text.UTF8Encoding]::new($false))
        } catch {
            # Log write failure is not fatal
        }
    }
}

#endregion

#region Path and evidence helpers (mirror existing harness conventions)

function Assert-ExistingPathChain([string] $Path, [string] $Label, [bool] $RequireFile = $false) {
    $full = [IO.Path]::GetFullPath($Path)
    if (-not [IO.Path]::IsPathRooted($full) -or $full.StartsWith('\\')) { throw "$Label must be a local rooted path" }
    if (-not (Test-Path -LiteralPath $full)) { throw "$Label does not exist" }
    $item = Get-Item -LiteralPath $full -ErrorAction Stop
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "$Label is a reparse point" }
    if ($RequireFile -and $item -isnot [IO.FileInfo]) { throw "$Label must be a regular file" }
    if ($item -is [IO.FileInfo]) {
        $cursor = $item.Directory
    } elseif ($item -is [IO.DirectoryInfo]) {
        $cursor = $item
    } else {
        throw "$Label is not a regular file or directory"
    }
    while ($null -ne $cursor) {
        if ($cursor -isnot [IO.DirectoryInfo]) { throw "$Label ancestry is not a directory" }
        if (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "$Label has a reparse-point ancestor: $($cursor.FullName)" }
        $parent = $cursor.Parent
        if ($null -eq $parent -or $parent.FullName -eq $cursor.FullName) { break }
        $cursor = $parent
    }
    return $item
}

function Assert-Descendant([string] $Root, [string] $Candidate, [string] $Label) {
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    $candidateFull = [IO.Path]::GetFullPath($Candidate)
    if (-not $candidateFull.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) { throw "$Label is outside the declared root" }
    return $candidateFull
}

function Assert-EvidenceRoot([string] $Path) {
    $item = Assert-ExistingPathChain $Path 'evidence root'
    if (-not $item.PSIsContainer) { throw 'evidence root must be a directory' }
    $driveRoot = [IO.Path]::GetPathRoot($item.FullName)
    if ([string]::IsNullOrEmpty($driveRoot)) { throw 'evidence root has no local volume root' }
    $drive = [IO.DriveInfo]::new($driveRoot)
    if (-not $drive.IsReady -or $drive.DriveType -ne [IO.DriveType]::Fixed -or $drive.VolumeLabel -ne 'S11BEVIDENCE') {
        throw 'evidence root must be on ready fixed guest-local volume S11BEVIDENCE'
    }
    return $item.FullName
}

function Write-ExclusiveText([string] $Path, [string] $Text) {
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $writer = [IO.StreamWriter]::new($stream, [Text.UTF8Encoding]::new($false))
        try { $writer.Write($Text) } finally { $writer.Dispose() }
    } finally { $stream.Dispose() }
}

#endregion

#region Volume resolution

function Resolve-EvidenceVolume {
    $drives = [IO.DriveInfo]::GetDrives()
    foreach ($drive in $drives) {
        try {
            if ($drive.IsReady -and $drive.DriveType -eq [IO.DriveType]::Fixed -and $drive.VolumeLabel -eq $script:EvidenceLabel) {
                return $drive.RootDirectory.FullName
            }
        } catch {
            # Drive might not be ready yet
        }
    }
    return $null
}

function Resolve-MediaVolume {
    $drives = [IO.DriveInfo]::GetDrives()
    foreach ($drive in $drives) {
        try {
            if ($drive.IsReady -and $drive.DriveType -eq [IO.DriveType]::CDRom) {
                return $drive.RootDirectory.FullName
            }
        } catch {
            # Drive might not be ready
        }
    }
    return $null
}

function Wait-ForEvidenceVolume {
    # Intentionally unbounded. This process is a resident watcher captured in a checkpoint's saved
    # RAM, so an absolute deadline computed here would be frozen in the snapshot; every checkpoint
    # revert happens much later, and Hyper-V Time Synchronization corrects the guest clock on resume,
    # so such a deadline would expire before the next evidence volume is attached. The host owns the
    # per-cycle budget: it hot-adds the volume, waits bounded for shutdown, and records a failed
    # cycle (leaving the guest up) when the guest does not shut down in time.
    $waitedSeconds = 0
    while ($true) {
        $root = Resolve-EvidenceVolume
        if ($root) { return $root }
        Start-Sleep -Seconds 2
        $waitedSeconds += 2
        if (($waitedSeconds % 30) -eq 0) {
            Write-WatcherLog "waiting for evidence volume '$script:EvidenceLabel' (${waitedSeconds}s of guest-active time)"
        }
    }
}

function Wait-ForMediaVolume {
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    while ([DateTime]::UtcNow -lt $deadline) {
        $root = Resolve-MediaVolume
        if ($root) { return $root }
        Start-Sleep -Seconds 2
    }
    throw 'CD-ROM media volume not found within 60s timeout'
}

function Wait-ForScenarioFile {
    param([string] $EvidenceRoot)
    $path = Join-Path $EvidenceRoot $script:ScenarioFileName
    $deadline = [DateTime]::UtcNow.AddSeconds($script:ScenarioWaitTimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $path) {
            return $path
        }
        Start-Sleep -Seconds 2
    }
    throw "$script:ScenarioFileName not found within $($script:ScenarioWaitTimeoutSeconds)s timeout"
}

#endregion

#region Scenario validation

function Read-AndValidateScenario {
    param([string] $ScenarioFilePath)
    $raw = [IO.File]::ReadAllText($ScenarioFilePath, [Text.Encoding]::UTF8)
    $scenario = $raw | ConvertFrom-Json

    if ($scenario.schema -ne $script:SchemaVersion) {
        throw "scenario.json schema mismatch: expected $script:SchemaVersion, got $($scenario.schema)"
    }
    if ([string]::IsNullOrWhiteSpace($scenario.scenario)) {
        throw 'scenario.json missing scenario name'
    }
    if ($scenario.scenario -notmatch $script:PhaseIdPattern) {
        throw 'scenario.json scenario name is unsafe'
    }
    if (-not $scenario.steps -or @($scenario.steps).Count -eq 0) {
        throw 'scenario.json has no steps'
    }
    if (@($scenario.steps).Count -gt 64) {
        throw 'scenario.json step count bound exceeded (max 64)'
    }

    $validKinds = @('setup', 'uninstall', 'capture', 'fixture-state-root', 'holder-start', 'holder-release', 'wait')
    foreach ($step in $scenario.steps) {
        if ([string]::IsNullOrWhiteSpace($step.kind)) { throw 'step missing kind' }
        if ($step.kind -notin $validKinds) { throw "unknown step kind: $($step.kind)" }
        switch ($step.kind) {
            'setup' {
                if ([string]::IsNullOrWhiteSpace($step.executable)) { throw 'setup step missing executable' }
                if ([string]::IsNullOrWhiteSpace($step.phase)) { throw 'setup step missing phase' }
                if ($step.phase -notmatch $script:PhaseIdPattern) { throw 'setup step phase is unsafe' }
                if ($step.executable -match '[\\/]' -or $step.executable -match '\.\.[\\/]') { throw 'setup executable must be a plain filename' }
            }
            'uninstall' {
                if ([string]::IsNullOrWhiteSpace($step.phase)) { throw 'uninstall step missing phase' }
                if ($step.phase -notmatch $script:PhaseIdPattern) { throw 'uninstall step phase is unsafe' }
            }
            'capture' {
                if ([string]::IsNullOrWhiteSpace($step.phase)) { throw 'capture step missing phase' }
                if ($step.phase -notmatch $script:PhaseIdPattern) { throw 'capture step phase is unsafe' }
                $logFromPhase = Get-ObjectProperty $step 'logFromPhase'
                if ($logFromPhase -and $logFromPhase -notmatch $script:PhaseIdPattern) { throw 'capture logFromPhase is unsafe' }
                $holderRecordFromPhase = Get-ObjectProperty $step 'holderRecordFromPhase'
                if ($holderRecordFromPhase -and $holderRecordFromPhase -notmatch $script:PhaseIdPattern) { throw 'capture holderRecordFromPhase is unsafe' }
            }
            'fixture-state-root' {
                $fixtureFiles = Get-ObjectProperty $step 'files'
                if (-not $fixtureFiles -or @($fixtureFiles).Count -eq 0) { throw 'fixture-state-root step missing files' }
                foreach ($f in $fixtureFiles) {
                    $fixtureRelativePath = Get-ObjectProperty $f 'relativePath'
                    $fixtureContent = Get-ObjectProperty $f 'content'
                    if ([string]::IsNullOrWhiteSpace($fixtureRelativePath)) { throw 'fixture file missing relativePath' }
                    if ($fixtureRelativePath -match '\.\.[\\/]') { throw 'fixture file relativePath is unsafe' }
                    if ($null -eq $fixtureContent) { throw 'fixture file missing content' }
                }
            }
            'holder-start' {
                if ([string]::IsNullOrWhiteSpace($step.guestFileName)) { throw 'holder-start missing guestFileName' }
                if ([string]::IsNullOrWhiteSpace($step.releaseSignalName)) { throw 'holder-start missing releaseSignalName' }
                if ([string]::IsNullOrWhiteSpace($step.phase)) { throw 'holder-start missing phase' }
                if ($step.phase -notmatch $script:PhaseIdPattern) { throw 'holder-start phase is unsafe' }
                if ($step.guestFileName -match '[\\/]' -or $step.guestFileName -match '\.\.[\\/]') { throw 'holder-start guestFileName must be a plain filename' }
                if ($step.releaseSignalName -match '[\\/]' -or $step.releaseSignalName -match '\.\.[\\/]') { throw 'holder-start releaseSignalName must be a plain filename' }
            }
            'holder-release' {
                if ([string]::IsNullOrWhiteSpace($step.releaseSignalName)) { throw 'holder-release missing releaseSignalName' }
                if ($step.releaseSignalName -match '[\\/]' -or $step.releaseSignalName -match '\.\.[\\/]') { throw 'holder-release releaseSignalName must be a plain filename' }
            }
            'wait' {
                if (-not $step.milliseconds -or $step.milliseconds -le 0) { throw 'wait step missing or invalid milliseconds' }
                if ($step.milliseconds -gt $script:WaitStepMaxMs) { throw "wait step milliseconds exceeds bound ($($script:WaitStepMaxMs))" }
            }
        }
        $expectFailureValue = Get-ObjectProperty $step 'expectFailure'
        if ($null -ne $expectFailureValue -and $expectFailureValue -isnot [bool]) { throw 'step expectFailure must be a boolean when present' }
    }

    $declaredAnswers = Get-ObjectProperty $scenario 'dialogAnswers'
    if ($declaredAnswers) {
        foreach ($answer in $declaredAnswers) {
            $answerMatch = Get-ObjectProperty $answer 'match'
            $answerValue = Get-ObjectProperty $answer 'answer'
            if ([string]::IsNullOrWhiteSpace($answerMatch)) { throw 'dialog answer missing match text' }
            if ([string]::IsNullOrWhiteSpace($answerValue)) { throw 'dialog answer missing answer value' }
            if ($answerValue -notin @('YES', 'NO', 'CANCEL')) { throw "dialog answer must be YES, NO, or CANCEL; got $answerValue" }
        }
    }

    return $scenario
}

#endregion

#region Process tree and dialog answering

function Get-DescendantProcessIds {
    param([int] $RootProcessId)
    $result = [Collections.Generic.HashSet[int]]::new()
    $result.Add($RootProcessId) | Out-Null
    $changed = $true
    $iterations = 0
    while ($changed -and $iterations -lt 50) {
        $changed = $false
        $iterations++
        try {
            $processes = Get-CimInstance -ClassName Win32_Process -ErrorAction SilentlyContinue
            foreach ($p in $processes) {
                $ppid = [int]$p.ParentProcessId
                $pid = [int]$p.ProcessId
                if ($result.Contains($ppid) -and -not $result.Contains($pid)) {
                    $result.Add($pid) | Out-Null
                    $changed = $true
                }
            }
        } catch {
            break
        }
    }
    return $result
}

function Scan-ForDialogs {
    param(
        [Collections.Generic.HashSet[int]] $DescendantPids,
        [System.Collections.ArrayList] $DeclaredAnswers
    )
    $scanner = [S11B.DialogScanResult]::new()
    $scanner.DescendantPids = $DescendantPids
    # The C# field is List<DialogAnswerSpec>; a PowerShell ArrayList does not convert implicitly, so
    # build the typed list explicitly. An empty declared set is a valid empty list, and an undeclared
    # dialog must still be detected in that case.
    $typedAnswers = [System.Collections.Generic.List[S11B.DialogAnswerSpec]]::new()
    if ($DeclaredAnswers) {
        foreach ($declaredAnswer in $DeclaredAnswers) { $typedAnswers.Add($declaredAnswer) | Out-Null }
    }
    $scanner.Answers = $typedAnswers

    # Windows PowerShell 5.1 cannot cast a PSMethod to a delegate type, so bind the .NET method
    # directly; a $scanner.EnumCallback cast throws "Cannot convert ... PSMethod to ... EnumWindowsProc".
    $method = $scanner.GetType().GetMethod('EnumCallback')
    $callback = [System.Delegate]::CreateDelegate([S11B.WatcherNative+EnumWindowsProc], $scanner, $method)
    try {
        [S11B.WatcherNative]::EnumWindows($callback, [IntPtr]::Zero) | Out-Null
    } catch {
        # EnumWindows failure is not fatal; treat as no dialog found
    }
    return $scanner
}

function Wait-AndAnswerDialogs {
    param(
        [System.Diagnostics.Process] $ChildProcess,
        [System.Collections.ArrayList] $DeclaredAnswers,
        [string] $StepDescription
    )
    $answered = $false
    $undeclaredDetected = $false
    $undeclaredText = ''
    $deadline = [DateTime]::UtcNow.AddSeconds($script:DialogTimeoutSeconds)

    while (-not $ChildProcess.HasExited -and [DateTime]::UtcNow -lt $deadline) {
        $descendantPids = Get-DescendantProcessIds $ChildProcess.Id
        $scan = Scan-ForDialogs $descendantPids $DeclaredAnswers

        if ($scan.UndeclaredHwnd -ne [IntPtr]::Zero) {
            $undeclaredDetected = $true
            $undeclaredText = $scan.UndeclaredText
            break
        }

        if ($scan.MatchedHwnd -ne [IntPtr]::Zero -and -not $answered) {
            Write-WatcherLog "answering declared dialog (button=$($scan.MatchedButtonId)) for $StepDescription"
            [S11B.WatcherNative]::PostMessage($scan.MatchedHwnd, [S11B.WatcherNative]::WM_COMMAND, $scan.MatchedButtonId, 0) | Out-Null
            $answered = $true
        }

        Start-Sleep -Milliseconds $script:DialogPollIntervalMs
    }

    return [ordered]@{
        answered          = $answered
        undeclaredDialog  = $undeclaredDetected
        undeclaredText    = $undeclaredText
    }
}

#endregion

#region Step execution

function Find-RunRecord {
    param([string] $EvidenceRoot, [string] $ScenarioName, [string] $Phase)
    $phaseRoot = Join-Path $EvidenceRoot "$ScenarioName\$Phase"
    if (-not (Test-Path -LiteralPath $phaseRoot)) {
        throw "phase directory not found for logFromPhase/holderRecordFromPhase: $phaseRoot"
    }
    $runDirs = @(Get-ChildItem -LiteralPath $phaseRoot -Directory -ErrorAction Stop | Where-Object { $_.Name -like 'run-*' })
    if ($runDirs.Count -ne 1) {
        throw "expected exactly one run directory in $phaseRoot, found $($runDirs.Count)"
    }
    $recordPath = Join-Path $runDirs[0].FullName 'run-record.json'
    if (-not (Test-Path -LiteralPath $recordPath)) {
        throw "run-record.json not found in $($runDirs[0].FullName)"
    }
    $raw = [IO.File]::ReadAllText($recordPath, [Text.Encoding]::UTF8)
    return @{ Record = ($raw | ConvertFrom-Json); RecordPath = $recordPath; RunDir = $runDirs[0].FullName }
}

function Build-HarnessCommand {
    param(
        [string] $ScriptPath,
        [hashtable] $NamedParams,
        [string[]] $ArrayParams
    )
    $parts = [System.Collections.ArrayList]::new()
    $escapedScript = $ScriptPath -replace "'", "''"
    $parts.Add("& '$escapedScript'") | Out-Null
    foreach ($key in ($NamedParams.Keys | Sort-Object)) {
        $value = $NamedParams[$key]
        $escapedKey = $key -replace "'", "''"
        if ($value -is [string]) {
            $escapedValue = $value -replace "'", "''"
            $parts.Add("-$escapedKey '$escapedValue'") | Out-Null
        } elseif ($value -is [bool]) {
            if ($value) { $parts.Add("-$escapedKey") | Out-Null }
        } else {
            $parts.Add("-$escapedKey $value") | Out-Null
        }
    }
    if ($ArrayParams -and $ArrayParams.Count -gt 0) {
        $literals = $ArrayParams | ForEach-Object { "'$($_ -replace "'", "''")'" }
        $parts.Add("-ArgumentList $($literals -join ',')") | Out-Null
    }
    return $parts -join ' '
}

function Invoke-SetupStep {
    param(
        $Step,
        [string] $EvidenceRoot,
        [string] $MediaRoot,
        [string] $ScenarioName,
        [System.Collections.ArrayList] $DialogAnswers
    )
    $harnessPath = Join-Path $MediaRoot 'guest\run-setup-uninstall.ps1'
    if (-not (Test-Path -LiteralPath $harnessPath)) { throw "harness not found: $harnessPath" }
    $executablePath = Join-Path $MediaRoot "setups\$($Step.executable)"
    if (-not (Test-Path -LiteralPath $executablePath)) { throw "setup executable not found: $executablePath" }

    $argList = @()
    $argumentList = Get-ObjectProperty $Step 'argumentList'
    if ($argumentList) { $argList = @($argumentList) }

    $named = [ordered]@{
        Kind              = 'setup'
        ReadOnlyMediaRoot = $MediaRoot.TrimEnd('\')
        ExecutablePath    = $executablePath
        EvidenceRoot      = $EvidenceRoot.TrimEnd('\')
        Scenario          = $ScenarioName
        Phase             = $Step.phase
    }
    $command = Build-HarnessCommand $harnessPath $named $argList

    Write-WatcherLog "starting setup: $($Step.executable) phase=$($Step.phase)"
    $process = Start-Process -FilePath 'powershell.exe' `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $command) `
        -PassThru

    $dialogResult = Wait-AndAnswerDialogs $process $DialogAnswers "setup/$($Step.phase)"
    if ($dialogResult.undeclaredDialog) {
        $process.WaitForExit(5000) | Out-Null
        throw "UNDECLARED_DIALOG: text='$($dialogResult.undeclaredText)' in setup/$($Step.phase)"
    }

    $process.WaitForExit([int]([TimeSpan]::FromMinutes(15).TotalMilliseconds)) | Out-Null
    if (-not $process.HasExited) { throw "setup/$($Step.phase) timed out after 15 minutes" }

    Write-WatcherLog "setup/$($Step.phase) exited with code $($process.ExitCode)"
    return [ordered]@{
        kind           = 'setup'
        phase          = $Step.phase
        executable     = $Step.executable
        exitCode       = [int]$process.ExitCode
        dialogAnswered = $dialogResult.answered
    }
}

function Invoke-UninstallStep {
    param(
        $Step,
        [string] $EvidenceRoot,
        [string] $ScenarioName,
        [System.Collections.ArrayList] $DialogAnswers
    )
    $harnessPath = Join-Path $script:MediaRoot 'guest\run-setup-uninstall.ps1'
    if (-not (Test-Path -LiteralPath $harnessPath)) { throw "harness not found: $harnessPath" }

    # Resolve uninstaller path from registry (mirrors run-setup-uninstall.ps1)
    $uninstallSubkey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{55D372A6-1DA5-41BE-B7AB-65CAB362E620}_is1'
    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
        [Microsoft.Win32.RegistryHive]::CurrentUser,
        [Microsoft.Win32.RegistryView]::Default)
    try {
        $key = $base.OpenSubKey($uninstallSubkey, $false)
        if ($null -eq $key) { throw 'exact production uninstall key is absent' }
        try {
            $value = $key.GetValue('UninstallString', $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
            if ($value -isnot [string]) { throw 'exact production UninstallString is not a string' }
            $regexMatch = [regex]::Match($value, '^\s*"([^"]+)"\s*$')
            if (-not $regexMatch.Success) { throw 'exact production UninstallString is not one quoted executable path' }
            $executablePath = $regexMatch.Groups[1].Value
        } finally { $key.Dispose() }
    } finally { $base.Dispose() }

    $argList = @()
    $argumentList = Get-ObjectProperty $Step 'argumentList'
    if ($argumentList) { $argList = @($argumentList) }

    $named = [ordered]@{
        Kind           = 'uninstall'
        ExecutablePath = $executablePath
        EvidenceRoot   = $EvidenceRoot.TrimEnd('\')
        Scenario       = $ScenarioName
        Phase          = $Step.phase
    }
    $command = Build-HarnessCommand $harnessPath $named $argList

    Write-WatcherLog "starting uninstall phase=$($Step.phase)"
    $process = Start-Process -FilePath 'powershell.exe' `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $command) `
        -PassThru

    $dialogResult = Wait-AndAnswerDialogs $process $DialogAnswers "uninstall/$($Step.phase)"
    if ($dialogResult.undeclaredDialog) {
        $process.WaitForExit(5000) | Out-Null
        throw "UNDECLARED_DIALOG: text='$($dialogResult.undeclaredText)' in uninstall/$($Step.phase)"
    }

    $process.WaitForExit([int]([TimeSpan]::FromMinutes(15).TotalMilliseconds)) | Out-Null
    if (-not $process.HasExited) { throw "uninstall/$($Step.phase) timed out after 15 minutes" }

    Write-WatcherLog "uninstall/$($Step.phase) exited with code $($process.ExitCode)"
    return [ordered]@{
        kind           = 'uninstall'
        phase          = $Step.phase
        exitCode       = [int]$process.ExitCode
        dialogAnswered = $dialogResult.answered
    }
}

function Invoke-CaptureStep {
    param(
        $Step,
        [string] $EvidenceRoot,
        [string] $MediaRoot,
        [string] $ScenarioName
    )
    $harnessPath = Join-Path $MediaRoot 'guest\capture-state.ps1'
    if (-not (Test-Path -LiteralPath $harnessPath)) { throw "harness not found: $harnessPath" }

    $commandParts = [System.Collections.ArrayList]::new()
    $escapedHarness = $harnessPath -replace "'", "''"
    $commandParts.Add("& '$escapedHarness'") | Out-Null
    $commandParts.Add("-EvidenceRoot '$($EvidenceRoot.TrimEnd("'") -replace "'", "''")'") | Out-Null
    $commandParts.Add("-Scenario '$ScenarioName'") | Out-Null
    $commandParts.Add("-Phase '$($Step.phase)'") | Out-Null

    $logFromPhase = Get-ObjectProperty $Step 'logFromPhase'
    if ($logFromPhase) {
        $runInfo = Find-RunRecord $EvidenceRoot $ScenarioName $logFromPhase
        $record = $runInfo.Record
        $exactLog = Get-ObjectProperty $record 'exactLog'
        $exactLogPresent = Get-ObjectProperty $exactLog 'present'
        $exactLogPath = Get-ObjectProperty $exactLog 'path'
        if ($exactLog -and $exactLogPresent -and -not [string]::IsNullOrWhiteSpace($exactLogPath)) {
            $escapedLog = [string]$exactLogPath -replace "'", "''"
            $commandParts.Add("-LogPath '$escapedLog'") | Out-Null
        }
    }
    $holderRecordFromPhase = Get-ObjectProperty $Step 'holderRecordFromPhase'
    if ($holderRecordFromPhase) {
        $holderPhaseRoot = Join-Path $EvidenceRoot "$ScenarioName\$holderRecordFromPhase"
        $holderPaths = @()
        $holderStartPath = Join-Path $holderPhaseRoot 'holder-start.json'
        if (Test-Path -LiteralPath $holderStartPath) { $holderPaths += $holderStartPath }
        $holderEndPath = Join-Path $holderPhaseRoot 'holder-end.json'
        if (Test-Path -LiteralPath $holderEndPath) { $holderPaths += $holderEndPath }
        if ($holderPaths.Count -gt 0) {
            $literals = $holderPaths | ForEach-Object { "'$($_ -replace "'", "''")'" }
            $commandParts.Add("-HolderRecordPath $($literals -join ',')") | Out-Null
        }
    }

    $command = $commandParts -join ' '
    Write-WatcherLog "starting capture phase=$($Step.phase)"
    $process = Start-Process -FilePath 'powershell.exe' `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $command) `
        -PassThru
    $process.WaitForExit([int]([TimeSpan]::FromMinutes(5).TotalMilliseconds)) | Out-Null
    if (-not $process.HasExited) { throw "capture/$($Step.phase) timed out after 5 minutes" }

    Write-WatcherLog "capture/$($Step.phase) exited with code $($process.ExitCode)"
    return [ordered]@{
        kind     = 'capture'
        phase    = $Step.phase
        exitCode = [int]$process.ExitCode
    }
}

function Invoke-FixtureStateRootStep {
    param($Step)
    $localAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
    $stateRoot = Join-Path $localAppData 'yasb-limitora'

    if (-not (Test-Path -LiteralPath $stateRoot)) {
        New-Item -ItemType Directory -Path $stateRoot | Out-Null
    }
    Assert-ExistingPathChain $stateRoot 'state root fixture' | Out-Null

    foreach ($file in $Step.files) {
        $filePath = Join-Path $stateRoot $file.relativePath
        $parentDir = [IO.Path]::GetDirectoryName($filePath)
        if ($parentDir -ne $stateRoot -and -not (Test-Path -LiteralPath $parentDir)) {
            New-Item -ItemType Directory -Path $parentDir | Out-Null
        }
        if (Test-Path -LiteralPath $filePath) {
            throw "fixture file already exists: $filePath"
        }
        Write-ExclusiveText $filePath ([string]$file.content)
    }

    Write-WatcherLog "fixture-state-root: created $(@($Step.files).Count) file(s) under $stateRoot"
    return [ordered]@{
        kind      = 'fixture-state-root'
        exitCode  = 0
        stateRoot = $stateRoot
        fileCount = @($Step.files).Count
    }
}

function Invoke-HolderStartStep {
    param(
        $Step,
        [string] $EvidenceRoot,
        [string] $MediaRoot,
        [string] $ScenarioName
    )
    $harnessPath = Join-Path $MediaRoot 'guest\hold-locked-file.ps1'
    if (-not (Test-Path -LiteralPath $harnessPath)) { throw "harness not found: $harnessPath" }

    $localAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
    $appRoot = Join-Path $localAppData 'Programs\yasb-limitora'
    $guestFile = Join-Path $appRoot $Step.guestFileName
    $releaseSignal = Join-Path $appRoot $Step.releaseSignalName

    if (-not (Test-Path -LiteralPath $guestFile)) { throw "holder guest file not found: $guestFile" }

    $named = [ordered]@{
        GuestFile     = $guestFile
        GuestRoot     = $appRoot
        ReleaseSignal = $releaseSignal
        EvidenceRoot  = $EvidenceRoot.TrimEnd('\')
        Scenario      = $ScenarioName
        Phase         = $Step.phase
    }
    $command = Build-HarnessCommand $harnessPath $named @()

    Write-WatcherLog "starting holder phase=$($Step.phase) file=$guestFile"
    $process = Start-Process -FilePath 'powershell.exe' `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $command) `
        -PassThru

    # Give the holder a moment to open the file
    Start-Sleep -Seconds 2
    if ($process.HasExited) {
        throw "holder/$($Step.phase) exited prematurely with code $($process.ExitCode)"
    }

    $script:HolderProcess = $process
    Write-WatcherLog "holder/$($Step.phase) running (PID=$($process.Id))"
    return [ordered]@{
        kind      = 'holder-start'
        phase     = $Step.phase
        processId = [int]$process.Id
        exitCode  = $null
    }
}

function Invoke-HolderReleaseStep {
    param($Step)
    $localAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
    $appRoot = Join-Path $localAppData 'Programs\yasb-limitora'
    $releaseSignal = Join-Path $appRoot $Step.releaseSignalName

    if (Test-Path -LiteralPath $releaseSignal) {
        throw "release signal already exists: $releaseSignal"
    }

    Write-ExclusiveText $releaseSignal "released $($Step.releaseSignalName) $([DateTime]::UtcNow.ToString('o'))`n"
    Write-WatcherLog "holder-release: created signal $releaseSignal"

    # Wait for the holder process to exit
    if ($script:HolderProcess -and -not $script:HolderProcess.HasExited) {
        $script:HolderProcess.WaitForExit(30000) | Out-Null
        if (-not $script:HolderProcess.HasExited) {
            throw 'holder did not exit within 30s of release signal'
        }
        Write-WatcherLog "holder exited with code $($script:HolderProcess.ExitCode)"
    }

    return [ordered]@{
        kind          = 'holder-release'
        releaseSignal = $releaseSignal
        exitCode      = 0
    }
}

function Invoke-WaitStep {
    param($Step)
    $ms = [int]$Step.milliseconds
    Write-WatcherLog "wait: sleeping $ms ms"
    Start-Sleep -Milliseconds $ms
    return [ordered]@{
        kind         = 'wait'
        milliseconds = $ms
        exitCode     = 0
    }
}

#endregion

#region Done record

function Write-DoneRecord {
    param(
        [string] $EvidenceRoot,
        [string] $ScenarioName,
        [string] $Result,
        [string] $FailureReason,
        [array] $StepResults,
        [string] $StartedUtc,
        [bool] $ShutdownSkipped
    )
    $done = [ordered]@{
        schema          = $script:DoneSchemaVersion
        scenario        = $ScenarioName
        startedUtc      = $StartedUtc
        finishedUtc     = [DateTime]::UtcNow.ToString('o')
        result          = $Result
        shutdownSkipped = $ShutdownSkipped
        steps           = @($StepResults)
    }
    if ($FailureReason) {
        $done.failureReason = $FailureReason
    }

    $donePath = Join-Path $EvidenceRoot $script:DoneFileName
    if (Test-Path -LiteralPath $donePath) {
        throw "done.json already exists: $donePath"
    }
    Write-ExclusiveText $donePath (($done | ConvertTo-Json -Depth 12) + "`n")
    Write-WatcherLog "wrote $donePath (result=$Result)"
}

#endregion

#region Main

function Test-StepFailure {
    # Returns $true when a step's recorded result must fail the cycle. A step may declare
    # expectFailure ($true in the manifest), which is how the fault scenarios state that a non-zero
    # exit is the injected outcome rather than an unexpected harness failure; the evidence (the fault
    # marker/exception plus the captured state) is what the independent verifier judges.
    param($Step, $StepResult)
    if (-not $StepResult) { return $false }
    $exitCode = Get-ObjectProperty $StepResult 'exitCode'
    if ($null -eq $exitCode) { return $false }
    if ([int]$exitCode -eq 0) { return $false }
    if ([bool](Get-ObjectProperty $Step 'expectFailure')) {
        Write-WatcherLog "step $($Step.kind)/$($Step.phase) exited with code $exitCode as declared (expectFailure)" 'WARN'
        return $false
    }
    return $true
}

$script:HolderProcess = $null
$script:MediaRoot = $null
$script:LogPath = $null
$evidenceRoot = $null
$scenarioName = $null
$startedUtc = $null
$stepResults = [System.Collections.ArrayList]::new()

try {
    Write-WatcherLog 'watcher starting'

    # 1. Wait for evidence volume
    $evidenceRoot = Wait-ForEvidenceVolume
    $evidenceRoot = Assert-EvidenceRoot $evidenceRoot
    Write-WatcherLog "evidence volume resolved: $evidenceRoot"

    $script:LogPath = Join-Path $evidenceRoot $script:LogFileName
    Write-WatcherLog "log file: $script:LogPath"

    # 1b. Declare the running build and refuse a stale-medium mismatch.
    $selfSha = Get-SelfSha256
    Write-WatcherLog "watcher script sha256=$selfSha"
    $stampPath = Join-Path $evidenceRoot 'expected-watcher.sha256'
    if (Test-Path -LiteralPath $stampPath) {
        $expectedSha = ([IO.File]::ReadAllText($stampPath, [Text.Encoding]::UTF8)).Trim().ToLowerInvariant()
        if ($selfSha -and $expectedSha -and $selfSha -ne $expectedSha) {
            throw "watcher build mismatch: running $selfSha but the evidence volume declares $expectedSha; the guest is reading a stale medium"
        }
        Write-WatcherLog "watcher build matches the declared stamp ($expectedSha)"
    } else {
        Write-WatcherLog 'no expected-watcher.sha256 stamp on the evidence volume; build identity not checked' 'WARN'
    }

    # 2. Wait for scenario.json
    $scenarioPath = Wait-ForScenarioFile $evidenceRoot
    Write-WatcherLog "scenario file found: $scenarioPath"

    # 3. Read and validate
    $scenario = Read-AndValidateScenario $scenarioPath
    $scenarioName = [string]$scenario.scenario
    Write-WatcherLog "scenario: $scenarioName"

    # 4. Check scenario directory doesn't exist
    $scenarioDir = Join-Path $evidenceRoot $scenarioName
    if (Test-Path -LiteralPath $scenarioDir) {
        throw "scenario directory already exists: $scenarioDir; evidence overwrite refused"
    }

    # 5. Resolve media volume
    $script:MediaRoot = Wait-ForMediaVolume
    $script:MediaRoot = $script:MediaRoot.TrimEnd('\')
    Write-WatcherLog "media volume resolved: $script:MediaRoot"

    # Build declared dialog answers
    $dialogAnswers = [System.Collections.ArrayList]::new()
    $declaredAnswers = Get-ObjectProperty $scenario 'dialogAnswers'
    if ($declaredAnswers) {
        foreach ($answer in $declaredAnswers) {
            $answerMatch = [string](Get-ObjectProperty $answer 'match')
            $answerValue = [string](Get-ObjectProperty $answer 'answer')
            $buttonId = switch ($answerValue) {
                'YES'    { 6 }
                'NO'     { 7 }
                'CANCEL' { 2 }
            }
            $spec = [S11B.DialogAnswerSpec]::new()
            $spec.Match = $answerMatch
            $spec.ButtonId = $buttonId
            $dialogAnswers.Add($spec) | Out-Null
        }
    }

    # 6. Execute steps
    $startedUtc = [DateTime]::UtcNow.ToString('o')
    $overallResult = 'success'
    $failureReason = $null

    foreach ($step in $scenario.steps) {
        $stepStartedUtc = [DateTime]::UtcNow.ToString('o')
        try {
            $stepResult = $null
            switch ($step.kind) {
                'setup'              { $stepResult = Invoke-SetupStep $step $evidenceRoot $script:MediaRoot $scenarioName $dialogAnswers }
                'uninstall'          { $stepResult = Invoke-UninstallStep $step $evidenceRoot $scenarioName $dialogAnswers }
                'capture'            { $stepResult = Invoke-CaptureStep $step $evidenceRoot $script:MediaRoot $scenarioName }
                'fixture-state-root' { $stepResult = Invoke-FixtureStateRootStep $step }
                'holder-start'       { $stepResult = Invoke-HolderStartStep $step $evidenceRoot $script:MediaRoot $scenarioName }
                'holder-release'     { $stepResult = Invoke-HolderReleaseStep $step }
                'wait'               { $stepResult = Invoke-WaitStep $step }
            }
            if ($stepResult) {
                if ($stepResult -is [array]) {
                    # Stray pipeline output from a step (for example a bool returned by a .NET
                    # WaitForExit call) would otherwise turn the result into an array and break the
                    # startedUtc/finishedUtc stamping below. The step contract puts its result object
                    # last, so keep it and record the stray output instead of failing the cycle.
                    Write-WatcherLog "step $($step.kind)/$($step.phase): stray pipeline output ($($stepResult.Count - 1) item(s)) before the result object; using the last item" 'WARN'
                    $stepResult = $stepResult[-1]
                }
                $stepResult.startedUtc = $stepStartedUtc
                $stepResult.finishedUtc = [DateTime]::UtcNow.ToString('o')
                $stepResults.Add($stepResult) | Out-Null
            }

            # Check exit code for steps that produce one; a declared expectFailure step may exit
            # non-zero without failing the cycle (see Test-StepFailure).
            if (Test-StepFailure $step $stepResult) {
                $overallResult = 'fail-closed'
                $failureReason = "step $($step.kind)/$($step.phase) exited with code $($stepResult.exitCode)"
                Write-WatcherLog "FAIL-CLOSED: $failureReason" 'ERROR'
                break
            }
        } catch {
            $overallResult = 'fail-closed'
            $failureReason = $_.Exception.Message
            Write-WatcherLog "FAIL-CLOSED: $failureReason" 'ERROR'
            $errorResult = [ordered]@{
                kind        = $step.kind
                phase       = $step.phase
                exitCode    = $null
                error       = $failureReason
                startedUtc  = $stepStartedUtc
                finishedUtc = [DateTime]::UtcNow.ToString('o')
            }
            $stepResults.Add($errorResult) | Out-Null
            break
        }
    }

    # 7. Write done.json
    $shutdownWhenDone = [bool](Get-ObjectProperty $scenario 'shutdownWhenDone')
    $shutdownSkipped = ($overallResult -ne 'success') -or (-not $shutdownWhenDone)
    Write-DoneRecord $evidenceRoot $scenarioName $overallResult $failureReason @($stepResults) $startedUtc $shutdownSkipped

    # 8. Shut down on success
    if ($overallResult -eq 'success' -and $shutdownWhenDone) {
        Write-WatcherLog 'shutting down guest'
        Stop-Computer -Force
    } else {
        Write-WatcherLog "not shutting down (result=$overallResult, shutdownWhenDone=$shutdownWhenDone)"
    }

} catch {
    $errorMessage = $_.Exception.Message
    Write-WatcherLog "FATAL: $errorMessage" 'ERROR'

    # Try to write done.json if we have the evidence root
    try {
        if ($evidenceRoot -and (Test-Path -LiteralPath $evidenceRoot)) {
            $donePath = Join-Path $evidenceRoot $script:DoneFileName
            if (-not (Test-Path -LiteralPath $donePath)) {
                $fatalDone = [ordered]@{
                    schema          = $script:DoneSchemaVersion
                    scenario        = $(if ($scenarioName) { $scenarioName } else { 'unknown' })
                    startedUtc      = $(if ($startedUtc) { $startedUtc } else { [DateTime]::UtcNow.ToString('o') })
                    finishedUtc     = [DateTime]::UtcNow.ToString('o')
                    result          = 'fail-closed'
                    failureReason   = $errorMessage
                    shutdownSkipped = $true
                    steps           = @($stepResults)
                }
                Write-ExclusiveText $donePath (($fatalDone | ConvertTo-Json -Depth 12) + "`n")
            }
        }
    } catch {
        # Cannot write done.json; nothing more to do
    }

    # Do NOT shut down - fail-closed so the parent can inspect
}

#endregion
