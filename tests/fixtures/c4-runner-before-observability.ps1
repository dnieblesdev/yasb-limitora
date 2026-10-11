[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$EvidenceRoot,
    [Parameter(Mandatory = $true)][string]$ScenarioPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:AutomationReady = $true
$script:OriginalEvidenceRoot = $EvidenceRoot
$ScenarioPath = [IO.Path]::GetFullPath($ScenarioPath)
$InputRoot = [IO.Path]::GetDirectoryName($ScenarioPath)
$ManifestPath = Join-Path $InputRoot 'modern-path-proof.json'

function Get-Sha256([string]$Path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash([IO.File]::ReadAllBytes($Path)))).Replace('-', '').ToLowerInvariant()
    } finally { $sha.Dispose() }
}

function Assert-Identity([string]$Path, $Identity, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label is missing" }
    $item = Get-Item -LiteralPath $Path -ErrorAction Stop
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "$Label is a reparse point" }
    if ([int64]$item.Length -ne [int64]$Identity.size -or (Get-Sha256 $item.FullName) -ne [string]$Identity.sha256) {
        throw "$Label identity mismatch"
    }
    return $item
}

function Assert-PlainPathChain([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $volume = [IO.Path]::GetPathRoot($full)
    $current = $volume
    $parts = $full.Substring($volume.Length).Trim('\').Split('\', [StringSplitOptions]::RemoveEmptyEntries)
    foreach ($part in $parts) {
        $current = Join-Path $current $part
        if (-not (Test-Path -LiteralPath $current -PathType Container)) { throw 'evidence directory is missing or unsafe' }
        $item = Get-Item -LiteralPath $current -Force -ErrorAction Stop
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'evidence directory contains a reparse point' }
    }
    return $full
}

function New-OwnedOutputRoot([string]$EvidenceRoot, [string]$Leaf) {
    if ($Leaf -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$' -or $Leaf -eq '.' -or $Leaf -eq '..') { throw 'unsafe evidence route name' }
    $parent = Assert-PlainPathChain $EvidenceRoot
    if (-not ('ModernPath.OutputDirectory' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace ModernPath {
 public static class OutputDirectory {
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
  public static extern bool CreateDirectory(string path, IntPtr securityAttributes);
 }
}
'@
    }
    $route = Join-Path $parent $Leaf
    if (-not [ModernPath.OutputDirectory]::CreateDirectory($route, [IntPtr]::Zero)) { throw 'owned evidence output root could not be exclusively created' }
    [void](Assert-PlainPathChain $route)
    return [IO.Path]::GetFullPath($route)
}

function Assert-OwnedOutputPath([string]$RootPath, [string]$Path) {
    $root = Assert-PlainPathChain $RootPath
    $target = [IO.Path]::GetFullPath($Path)
    $prefix = $root.TrimEnd('\') + '\'
    if (-not $target.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'evidence path escapes owned output root' }
    $parent = [IO.Path]::GetDirectoryName($target)
    [void](Assert-PlainPathChain $parent)
    if (Test-Path -LiteralPath $target) {
        $item = Get-Item -LiteralPath $target -Force -ErrorAction Stop
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'evidence target is a reparse point' }
    }
    return $target
}

function Write-Record([string]$RootPath, [string]$Path, $Record) {
    $target = Assert-OwnedOutputPath $RootPath $Path
    $json = (($Record | ConvertTo-Json -Depth 12) + "`n")
    $bytes = ([Text.UTF8Encoding]::new($false)).GetBytes($json)
    $stream = [IO.File]::Open($target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
}

$script:OwnedFailureStages = @('Roots','app-root-guard','state-root-guard','route-guard','capture-baseline','setup-launch','setup-wait','setup-output-read','setup-cleanup','after-setup','registration','capture-before-uninstall','uninstall-launch','uninstall-wait','uninstall-output-read','uninstall-cleanup','after-uninstall','cleanup','summary','outcome','Other')
function Get-OwnedFailureClass([Exception]$Exception) {
    foreach ($type in @([IO.IOException],[UnauthorizedAccessException],[InvalidOperationException],[ArgumentException],[TimeoutException],[System.Security.SecurityException],[System.Management.Automation.PipelineStoppedException])) {
        if ($Exception -is $type) { return $type.Name }
    }
    return 'OtherException'
}
function Assert-OwnedDiagnosticRoot([string]$RootPath) {
    $full = Assert-PlainPathChain $RootPath
    $item = Get-Item -LiteralPath $full -Force -ErrorAction Stop
    if ($item -isnot [IO.DirectoryInfo] -or $item.Name -cne 'owned-cleanup') { throw 'diagnostic root is not an existing owned-cleanup route' }
    return $full
}
function Write-OwnedFailureDiagnostic([string]$RootPath,[string]$Stage,[string]$ExceptionClass,$Data) {
    if ($Stage -notin $script:OwnedFailureStages) { $Stage = 'Other' }
    if ($Data -is [Collections.IDictionary] -and $Data.Contains('stage') -and $Data['stage'] -notin $script:OwnedFailureStages) { $Stage = 'Other' }
    elseif ($null -ne $Data -and $null -ne $Data.PSObject.Properties['stage'] -and $Data.stage -notin $script:OwnedFailureStages) { $Stage = 'Other' }
    $allowed = @('IOException','UnauthorizedAccessException','InvalidOperationException','ArgumentException','TimeoutException','SecurityException','PipelineStoppedException')
    if ($ExceptionClass -notin $allowed) { $ExceptionClass = 'OtherException' }
    $root = Assert-OwnedDiagnosticRoot $RootPath
    $path = Join-Path $root 'failure-diagnostic.json'
    [void](Assert-OwnedOutputPath $root $path)
    $record = [ordered]@{schema='yasb-limitora.owned-cleanup-failure/v1';stage=$Stage;exceptionClass=$ExceptionClass;result='failed'}
    $bytes = ([Text.UTF8Encoding]::new($false)).GetBytes((($record | ConvertTo-Json -Compress) + "`n"))
    $stream = [IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { $stream.Write($bytes,0,$bytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
}

function Stop-OwnedProcess([System.Diagnostics.Process]$Process, [string]$ExpectedStartTime, [int]$WaitMilliseconds = 1500) {
    if ($WaitMilliseconds -lt 1) { throw 'process cleanup budget must be positive' }
    $Process.Refresh()
    if ($Process.HasExited) { return $true }
    $current = Get-Process -Id $Process.Id -ErrorAction SilentlyContinue
    if ($null -eq $current) { throw 'process identity changed; refusing cleanup' }
    try {
        if ($current.StartTime.ToUniversalTime().ToString('o') -cne $ExpectedStartTime) { throw 'process identity changed; refusing cleanup' }
        $script:OwnedCleanupObservation = [ordered]@{ pid = [int]$Process.Id; startTimeUtc = $ExpectedStartTime; outcome = 'kill-requested' }
        $current.Kill()
        if (-not $Process.WaitForExit($WaitMilliseconds)) { $script:OwnedCleanupObservation.outcome = 'timed-out'; throw 'owned process cleanup timed out' }
        $script:OwnedCleanupObservation.outcome = 'stopped'
        return $true
    } finally { $current.Dispose() }
}

function Invoke-BoundedDiscoveryWorker([int]$RootPid, [DateTime]$DeadlineUtc, [string]$WorkerPath, [Parameter(Mandatory = $true)][int64]$ExpectedWorkerSize, [Parameter(Mandatory = $true)][string]$ExpectedWorkerSha256, [ValidateSet('Cim', 'Stall')][string]$Provider = 'Cim') {
    if ($ExpectedWorkerSize -lt 1 -or $ExpectedWorkerSize -gt 1048576 -or $ExpectedWorkerSha256 -notmatch '^[0-9a-f]{64}$') { throw 'trusted process discovery worker identity is invalid' }
    $worker = Assert-Identity $WorkerPath @{ size = $ExpectedWorkerSize; sha256 = $ExpectedWorkerSha256 } 'process discovery worker'
    [void](Assert-PlainPathChain $worker.DirectoryName)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = Join-Path $PSHOME 'powershell.exe'
    $psi.Arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $worker.FullName + '" -RootPid ' + $RootPid + ' -Provider ' + $Provider
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $child = New-Object System.Diagnostics.Process
    $child.StartInfo = $psi
    $start = $null
    try {
        if ([DateTime]::UtcNow -ge $DeadlineUtc) { throw 'process discovery exceeded the shared deadline before launch' }
        if (-not $child.Start()) { throw 'process discovery worker did not start' }
        $start = $child.StartTime.ToUniversalTime().ToString('o')
        $errorRead = $child.StandardError.ReadToEndAsync()
        $script:DiscoveryWorkerObservation = [ordered]@{ pid = [int]$child.Id; startTimeUtc = $start; outcome = 'running' }
        $remaining = [int][Math]::Floor(($DeadlineUtc - [DateTime]::UtcNow).TotalMilliseconds)
        if ($remaining -le 0 -or -not $child.WaitForExit($remaining)) {
            Stop-OwnedProcess $child $start 1500 | Out-Null
            $script:DiscoveryWorkerObservation.outcome = 'stopped-after-deadline'
            throw 'process discovery exceeded the shared deadline'
        }
        $script:DiscoveryWorkerObservation.outcome = 'exited'
        $output = $child.StandardOutput.ReadToEnd()
        [void]$errorRead.GetAwaiter().GetResult()
        if ($child.ExitCode -ne 0 -or $output.Length -gt 65536) { throw 'process discovery worker failed or exceeded output bound' }
        try { return @(ConvertFrom-Json -InputObject $output -ErrorAction Stop) }
        catch { throw 'process discovery worker returned invalid data' }
    } finally {
        try {
            if ($child.Id -gt 0) {
                $child.Refresh()
                if (-not $child.HasExited) {
                    if ([string]::IsNullOrEmpty($start)) { throw 'discovery worker identity unavailable; refusing cleanup' }
                    Stop-OwnedProcess $child $start 1500 | Out-Null
                }
                [void](Assert-PlainPathChain $worker.DirectoryName)
                [void](Assert-Identity $WorkerPath @{ size = $ExpectedWorkerSize; sha256 = $ExpectedWorkerSha256 } 'process discovery worker')
            }
        } finally { $child.Dispose() }
    }
}

function Get-ProcessTreeIds([int]$RootPid, [DateTime]$DeadlineUtc, [string]$WorkerPath, [Parameter(Mandatory = $true)][int64]$ExpectedWorkerSize, [Parameter(Mandatory = $true)][string]$ExpectedWorkerSha256, [ValidateSet('Cim', 'Stall')][string]$Provider = 'Cim') {
    $pids = Invoke-BoundedDiscoveryWorker $RootPid $DeadlineUtc $WorkerPath $ExpectedWorkerSize $ExpectedWorkerSha256 $Provider
    $identities = [Collections.Generic.Dictionary[int,string]]::new()
    foreach ($entry in $pids) {
        if ([DateTime]::UtcNow -ge $DeadlineUtc) { throw 'process identity validation exceeded the shared deadline' }
        $id = [int]$entry.pid
        $process = Get-Process -Id $id -ErrorAction SilentlyContinue
        if ($null -eq $process) { continue }
        $observed = $process.StartTime.ToUniversalTime().ToString('o')
        if ($observed -cne [string]$entry.startTimeUtc) { throw 'process identity changed during discovery; refusing ownership' }
        $identities.Add($id, $observed)
    }
    if (-not $identities.ContainsKey($RootPid)) { throw 'requested root process ended during discovery' }
    return $identities
}

function Find-DeclaredDialog([Collections.Generic.Dictionary[int,string]]$ProcessIdentities, [string[]]$Matches) {
    if ($ProcessIdentities.Count -gt 128) { throw 'process tree exceeds dialog scan bound' }
    $identityStale = $false
    foreach ($entry in $ProcessIdentities.GetEnumerator()) {
        $process = Get-Process -Id $entry.Key -ErrorAction SilentlyContinue
        if ($null -eq $process) { $identityStale = $true; continue }
        try { if ($process.StartTime.ToUniversalTime().ToString('o',[Globalization.CultureInfo]::InvariantCulture) -cne $entry.Value) { $identityStale = $true } }
        catch { $identityStale = $true }
        finally { $process.Dispose() }
    }
    if (-not ('ModernPath.Native' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
using System.Diagnostics;
using System.Globalization;
namespace ModernPath {
 public static class Native {
  public delegate bool EnumProc(IntPtr hwnd, IntPtr data);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc callback, IntPtr data);
  [DllImport("user32.dll", CharSet=CharSet.Auto)] public static extern int GetClassName(IntPtr hwnd, StringBuilder text, int size);
  [DllImport("user32.dll", CharSet=CharSet.Auto)] public static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int size);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, EnumProc callback, IntPtr data);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hwnd, uint msg, IntPtr wparam, IntPtr lparam);
 }
 public sealed class Scan {
  public IntPtr Match = IntPtr.Zero, Unexpected = IntPtr.Zero;
  public int Answers, WindowsSeen, OwnedTextReads, ForeignWindows, OwnedWindows, MatchFragments;
  public bool Overflow, StaleIdentity;
  public string UnexpectedClass = "", MatchFragment = "";
  public System.Collections.Generic.Dictionary<int,string> Identities;
  public string[] Fragments;
  public bool Visit(IntPtr hwnd, IntPtr data) {
   if (++WindowsSeen > 1024) { Overflow = true; return false; }
   var cls = new StringBuilder(128); Native.GetClassName(hwnd, cls, cls.Capacity);
   uint rawPid; if (Native.GetWindowThreadProcessId(hwnd, out rawPid) == 0) return true;
   var pid = unchecked((int)rawPid); string expected;
   if (!Identities.TryGetValue(pid, out expected)) { ForeignWindows++; return true; }
   try {
    using (var process = Process.GetProcessById(pid)) {
     var actual = process.StartTime.ToUniversalTime().ToString("o", CultureInfo.InvariantCulture);
     if (!String.Equals(actual, expected, StringComparison.Ordinal)) { StaleIdentity = true; return true; }
    }
   } catch { StaleIdentity = true; return true; }
   OwnedWindows++; OwnedTextReads++;
   var title = new StringBuilder(4096); Native.GetWindowText(hwnd, title, title.Capacity);
   var text = new StringBuilder(title.ToString());
   var childCount = 0;
   Native.EnumChildWindows(hwnd, (child, ignored) => {
    if (++childCount > 128 || text.Length > 8192) { Overflow = true; return false; }
    uint childRawPid; if (Native.GetWindowThreadProcessId(child, out childRawPid) == 0 || unchecked((int)childRawPid) != pid) { StaleIdentity = true; return true; }
    try {
     using (var childProcess = Process.GetProcessById(pid)) {
      var childStart = childProcess.StartTime.ToUniversalTime().ToString("o", CultureInfo.InvariantCulture);
      if (!String.Equals(childStart, expected, StringComparison.Ordinal)) { StaleIdentity = true; return true; }
     }
    } catch { StaleIdentity = true; return true; }
    var part = new StringBuilder(512); Native.GetWindowText(child, part, part.Capacity);
    if (part.Length > 0) text.Append("\n").Append(part);
    return text.Length <= 8192;
   }, IntPtr.Zero);
   if (Overflow || text.Length > 8192) { Overflow = true; return false; }
   if (!String.Equals(cls.ToString(), "#32770", StringComparison.Ordinal) && !String.Equals(title.ToString(), "yasb-limitora uninstall", StringComparison.Ordinal)) return true;
   var found = new System.Collections.Generic.HashSet<string>(StringComparer.Ordinal);
   foreach (var fragment in Fragments) if (!String.IsNullOrWhiteSpace(fragment) && text.ToString().IndexOf(fragment, StringComparison.OrdinalIgnoreCase) >= 0) found.Add(fragment);
   if (found.Count > 0) {
    Answers++; if (Match == IntPtr.Zero) Match = hwnd;
    foreach (var fragment in found) { MatchFragments++; MatchFragment = fragment; }
    return true;
   }
   if (Unexpected == IntPtr.Zero) { Unexpected = hwnd; UnexpectedClass = cls.ToString(); }
   return true;
  }
 }
}
'@
    }
    $scan = [ModernPath.Scan]::new()
    $scan.Identities = $ProcessIdentities
    $scan.Fragments = $Matches
    $callback = [Delegate]::CreateDelegate([ModernPath.Native+EnumProc], $scan, $scan.GetType().GetMethod('Visit'))
    [void][ModernPath.Native]::EnumWindows($callback, [IntPtr]::Zero)
    if ($identityStale) { $scan.StaleIdentity = $true }
    if ($scan.Overflow) { throw 'dialog scan exceeded its bounded window or text budget' }
    return [pscustomobject]@{
        schema = 'yasb-limitora.owned-dialog-scan/v1'
        Match = $scan.Match; Unexpected = $scan.Unexpected; UnexpectedClass = $scan.UnexpectedClass
        Answers = [int]$scan.Answers; MatchFragments = [int]$scan.MatchFragments; MatchFragment = [string]$scan.MatchFragment
        Overflow = [bool]$scan.Overflow; StaleIdentity = [bool]$scan.StaleIdentity
        WindowsSeen = [int]$scan.WindowsSeen; OwnedWindows = [int]$scan.OwnedWindows
        ForeignWindows = [int]$scan.ForeignWindows; OwnedTextReads = [int]$scan.OwnedTextReads
    }
}

function Post-OwnedDialogAnswer([IntPtr]$Hwnd, [Collections.Generic.Dictionary[int,string]]$ProcessIdentities, [string[]]$Matches, [string]$Answer) {
    if ($Hwnd -eq [IntPtr]::Zero -or $ProcessIdentities.Count -gt 128) { throw 'invalid dialog action target' }
    $buttonId = switch -CaseSensitive ($Answer) { 'YES' { 6 } 'NO' { 7 } 'CANCEL' { 2 } default { throw 'undeclared dialog answer' } }
    $fresh = Find-DeclaredDialog $ProcessIdentities $Matches
    if ($fresh.StaleIdentity -or $fresh.Answers -ne 1 -or $fresh.MatchFragments -ne 1 -or $fresh.Match -ne $Hwnd -or $fresh.Unexpected -ne [IntPtr]::Zero) { throw "dialog target changed or became ambiguous before answer (answers=$($fresh.Answers), fragments=$($fresh.MatchFragments), match=$($fresh.Match), unexpected=$($fresh.Unexpected), stale=$($fresh.StaleIdentity))" }
    [uint32]$windowPid = 0
    [void][ModernPath.Native]::GetWindowThreadProcessId($Hwnd, [ref]$windowPid)
    $id = [int]$windowPid
    if (-not $ProcessIdentities.ContainsKey($id)) { throw 'dialog action target is not process-owned' }
    $process = Get-Process -Id $id -ErrorAction SilentlyContinue
    if ($null -eq $process -or $process.StartTime.ToUniversalTime().ToString('o') -cne $ProcessIdentities[$id]) { throw 'dialog action process identity is stale' }
    if (-not [ModernPath.Native]::PostMessage($Hwnd, 0x0111, [IntPtr]$buttonId, [IntPtr]::Zero)) { throw 'declared dialog action was not posted' }
}

function Invoke-OwnedUninstall([string]$Executable, [string[]]$Matches, [string]$Answer, [int]$TimeoutSeconds, [string]$WorkerPath, [string]$EvidenceRoot, [string]$EvidencePath, [Parameter(Mandatory = $true)][int64]$ExpectedWorkerSize, [Parameter(Mandatory = $true)][string]$ExpectedWorkerSha256, [string[]]$ChildArguments = @('/NORESTART'), [ValidateSet('Cim', 'Stall')][string]$DiscoveryProvider = 'Cim') {
    $proc = Start-Process -FilePath $Executable -ArgumentList $ChildArguments -PassThru
    $start = $proc.StartTime.ToUniversalTime().ToString('o')
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $answered = $false
    $processIdentities = $null
    $nextDiscoveryUtc = [DateTime]::MinValue
    try {
        while (-not $proc.HasExited -and [DateTime]::UtcNow -lt $deadline) {
            if ([DateTime]::UtcNow -ge $nextDiscoveryUtc) {
                $processIdentities = Get-ProcessTreeIds $proc.Id $deadline $WorkerPath $ExpectedWorkerSize $ExpectedWorkerSha256 $DiscoveryProvider
                $nextDiscoveryUtc = [DateTime]::UtcNow.AddMilliseconds(500)
            }
            $scan = Find-DeclaredDialog $processIdentities $Matches
            if ($scan.StaleIdentity) { throw 'process identity became stale; refusing dialog action' }
            if ($scan.Unexpected -ne [IntPtr]::Zero) { throw 'unexpected process-owned dialog; refusing automated answer' }
            if ($scan.Answers -gt 1 -or $scan.MatchFragments -gt 1) { throw 'ambiguous declared dialog match' }
            if ($scan.Match -ne [IntPtr]::Zero -and -not $answered) {
                if ($scan.Answers -ne 1 -or $scan.Unexpected -ne [IntPtr]::Zero) { throw 'dialog answer is ambiguous or accompanied by an unknown owned dialog' }
                $freshIdentities = Get-ProcessTreeIds $proc.Id $deadline $WorkerPath $ExpectedWorkerSize $ExpectedWorkerSha256 $DiscoveryProvider
                Post-OwnedDialogAnswer $scan.Match $freshIdentities $Matches $Answer
                $answered = $true
            }
            Start-Sleep -Milliseconds 200
        }
    } catch {
        $reason = $_.Exception.Message
        try { Stop-OwnedProcess $proc $start 1500 | Out-Null }
        catch { throw ('uninstaller handling failed and owned cleanup was refused or timed out: ' + $reason) }
        throw $reason
    }
    if (-not $proc.HasExited) {
        Stop-OwnedProcess $proc $start 1500 | Out-Null
        throw 'uninstaller timed out'
    }
    $result = [ordered]@{ phase = 'uninstall'; exitCode = [int]$proc.ExitCode; dialogAnswered = $answered; outcome = if ($proc.ExitCode -eq 0) { 'installer-success' } else { 'installer-nonzero' } }
    Write-Record $EvidenceRoot $EvidencePath $result
    if ($proc.ExitCode -ne 0) { throw 'uninstaller returned non-zero' }
    return $result
}

function Invoke-ModernOwnedCleanupRunner($Manifest) {
    $services = New-OwnedCleanupProductionServices $Manifest $EvidenceRoot
    Invoke-OwnedCleanupLifecycleCore $Manifest $EvidenceRoot $services
}

if (-not $script:AutomationReady) { throw 'runner execution disabled until consent and complete-capture gates are implemented and tested' }
try {
    $manifestFull = [IO.Path]::GetFullPath($ManifestPath)
    $inputRoot = [IO.Path]::GetDirectoryName($manifestFull)
    . (Join-Path $inputRoot 'manifest-validation.ps1')
    $manifest = Read-ModernProofManifest -InputRoot $inputRoot -ManifestPath $manifestFull
    $runnerPath = [IO.Path]::GetFullPath($manifest.Artifacts.runner.Path)
    if (-not [string]::Equals([IO.Path]::GetFullPath($PSCommandPath), $runnerPath, [StringComparison]::OrdinalIgnoreCase)) { throw 'executing runner path differs from the validated runner artifact' }
    [void](Assert-Identity $PSCommandPath @{ size = $manifest.Artifacts.runner.Size; sha256 = $manifest.Artifacts.runner.Sha256 } 'modern proof runner')
    . $manifest.Artifacts.jobModule.Path
    . $manifest.Artifacts.consentModule.Path
    . $manifest.Artifacts.captureModule.Path
    . $manifest.Artifacts.lifecycleModule.Path
    [void](Invoke-ModernOwnedCleanupRunner $manifest)
    exit 0
} catch {
    try {
        $existingRoute = Join-Path ([IO.Path]::GetFullPath($script:OriginalEvidenceRoot)) 'owned-cleanup'
        if (Test-Path -LiteralPath $existingRoute -PathType Container) { Write-OwnedFailureDiagnostic $existingRoute 'Other' (Get-OwnedFailureClass $_.Exception) $_.Exception.Data }
    } catch { }
    [Console]::Error.WriteLine('owned-cleanup lifecycle failed closed')
    exit 1
}
