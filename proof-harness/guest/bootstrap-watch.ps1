<#
.SYNOPSIS
    Universal resident guest bootstrap for reusable VM checkpoint runs.
.DESCRIPTION
    This is the only scenario-independent script installed on the guest OS disk before
    checkpoint freeze. Every run supplies runner.ps1 and its manifests on a fresh input
    volume; no runner, scenario, ISO, or setup media is captured in checkpoint RAM.

    The input volume is treated as read-only by policy: the watcher never writes to it,
    passes only read paths to the runner, and hashes the complete input tree before and
    after execution. A host-side read-only attachment is still required where supported.
    Any input mutation, missing/ambiguous label, path escape, reparse point, hash mismatch,
    artifact mismatch, or non-zero runner exit fails closed. Failures leave the guest up.
.NOTES
    Windows PowerShell 5.1 compatible and safe under StrictMode.
    Operator API: attach exactly one fixed volume labelled S11BINPUTS and one distinct
    fixed volume labelled S11BEVIDENCE. Input contains runner.ps1, scenario.json,
    expected-runner.sha256, and expected-artifacts.json. The runner receives
    -EvidenceRoot and -ScenarioPath. Only controlled success requests guest shutdown.
    -NoRun is for offline tests that dot-source helper functions; -NoShutdown is for
    harmless offline tests and must not be used for a proof run.
#>

[CmdletBinding()]
param(
    [switch] $NoRun,
    [switch] $Once,
    [switch] $NoShutdown,
    [ValidateRange(1, 60)]
    [int] $PollSeconds = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:InputLabel = 'S11BINPUTS'
$script:EvidenceLabel = 'S11BEVIDENCE'
$script:ReservedVolumeRootNames = @('SYSTEM VOLUME INFORMATION', '$RECYCLE.BIN')
$script:RunnerName = 'runner.ps1'
$script:ScenarioName = 'scenario.json'
$script:ExpectedRunnerName = 'expected-runner.sha256'
$script:ExpectedArtifactsName = 'expected-artifacts.json'
$script:DoneName = 'done.json'
$script:ExitName = 'exit.json'
$script:LogName = 'bootstrap.log'
$script:RunSchema = 'gentle-ai.yasb-limitora.reusable-vm-run/v1'
$script:ArtifactSchema = 'gentle-ai.yasb-limitora.reusable-artifact-manifest/v1'
$script:DoneSchema = 'gentle-ai.yasb-limitora.reusable-vm-done/v1'
$script:ExitSchema = 'gentle-ai.yasb-limitora.reusable-vm-exit/v1'
$script:MaxLogBytes = 1048576
$script:MaxInputFiles = 4096
$script:MaxArtifacts = 512
$script:MaxFileBytes = 1073741824
$script:MaxRunnerOutputChars = 1048576
$script:RunnerTimeoutSeconds = 300
$script:BootstrapPath = $PSCommandPath
$script:PollSeconds = $PollSeconds

function Get-ObjectProperty {
    param($Object, [string] $Name)
    if ($null -eq $Object) { return $null }
    if ($Object -is [System.Collections.IDictionary] -and $Object.Contains($Name)) {
        return $Object[$Name]
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Write-BoundedLog {
    param([string] $Path, [string] $Message, [string] $Level = 'INFO')
    $line = "$( [DateTime]::UtcNow.ToString('o') ) [$Level] $Message`n"
    Write-Host $line.TrimEnd()
    try {
        $old = if (Test-Path -LiteralPath $Path) {
            [IO.File]::ReadAllText($Path, [Text.Encoding]::UTF8)
        } else { '' }
        $content = $old + $line
        if ([Text.Encoding]::UTF8.GetByteCount($content) -gt $script:MaxLogBytes) {
            $content = '[log truncated]`n' + $content.Substring([math]::Max(0, $content.Length - 8192))
        }
        [IO.File]::WriteAllText($Path, $content, [Text.UTF8Encoding]::new($false))
    } catch {
        # Evidence writing is best effort during an already failing cycle.
    }
}

function Write-ExclusiveJson {
    param([string] $Path, $Object)
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $writer = [IO.StreamWriter]::new($stream, [Text.UTF8Encoding]::new($false))
        try { $writer.Write(($Object | ConvertTo-Json -Depth 12) + "`n") } finally { $writer.Dispose() }
    } finally { $stream.Dispose() }
}

function Test-ReservedVolumeRootName {
    param([string] $Name)
    return $script:ReservedVolumeRootNames -contains ([string]$Name).ToUpperInvariant()
}

function Get-Sha256 {
    param([string] $Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $stream = [IO.File]::OpenRead($Path)
        try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() } finally { $stream.Dispose() }
    } finally { $sha.Dispose() }
}

function Get-BootstrapSha256 {
    $path = $script:BootstrapPath
    if ([string]::IsNullOrWhiteSpace($path)) { throw 'bootstrap watcher source path is unavailable' }
    return Get-Sha256 $path
}

function Assert-ExistingPathChain {
    param([string] $Path, [string] $Label, [bool] $RequireFile = $false)
    $full = [IO.Path]::GetFullPath($Path)
    if (-not [IO.Path]::IsPathRooted($full) -or $full.StartsWith('\\')) { throw "$Label must be a local rooted path" }
    if (-not (Test-Path -LiteralPath $full)) { throw "$Label does not exist" }
    $item = Get-Item -LiteralPath $full -ErrorAction Stop
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "$Label is a reparse point" }
    if ($RequireFile -and $item -isnot [IO.FileInfo]) { throw "$Label must be a regular file" }
    if ($item -is [IO.FileInfo]) { $cursor = $item.Directory } elseif ($item -is [IO.DirectoryInfo]) { $cursor = $item } else { throw "$Label is not a regular file or directory" }
    while ($null -ne $cursor) {
        if ($cursor -isnot [IO.DirectoryInfo]) { throw "$Label ancestry is not a directory" }
        if (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "$Label has a reparse-point ancestor" }
        $parent = $cursor.Parent
        if ($null -eq $parent -or $parent.FullName -eq $cursor.FullName) { break }
        $cursor = $parent
    }
    return $item
}

function Assert-RelativePath {
    param([string] $Relative, [string] $Label)
    if ([string]::IsNullOrWhiteSpace($Relative) -or [IO.Path]::IsPathRooted($Relative)) { throw "$Label must be a relative path" }
    $parts = $Relative.Replace('\', '/').Split('/')
    if ($parts.Count -gt 32 -or $parts -contains '..' -or $parts -contains '') { throw "$Label contains an unsafe path" }
    if ($Relative.IndexOf([char]0) -ge 0 -or $Relative -match '[<>:"|?*]') { throw "$Label contains an invalid character" }
    return $Relative.Replace('/', '\')
}

function Get-CandidateVolumes {
    param([string] $Label)
    $candidates = @()
    foreach ($drive in [IO.DriveInfo]::GetDrives()) {
        try {
            if ($drive.IsReady -and $drive.DriveType -eq [IO.DriveType]::Fixed -and $drive.VolumeLabel -ceq $Label) {
                $candidates += [pscustomobject]@{
                    Root = $drive.RootDirectory.FullName
                    Label = $drive.VolumeLabel
                    VolumeId = $drive.RootDirectory.FullName.ToUpperInvariant()
                    Ready = $drive.IsReady
                    Fixed = ($drive.DriveType -eq [IO.DriveType]::Fixed)
                }
            }
        } catch { }
    }
    return $candidates
}

function Resolve-UniqueVolume {
    param([Parameter(Mandatory = $true)][string] $Label, [object[]] $Candidates = $null)
    if ($null -eq $Candidates) {
        $discovered = @(Get-CandidateVolumes -Label $Label)
        if ($discovered.Count -eq 1 -and $discovered[0] -is [System.Array]) {
            $Candidates = @($discovered[0])
        } else {
            $Candidates = $discovered
        }
    } else {
        $Candidates = @($Candidates)
    }
    $valid = @($Candidates | Where-Object {
        $_ -and [string]::Equals([string](Get-ObjectProperty $_ 'Label'), $Label, [StringComparison]::Ordinal) -and
        [bool](Get-ObjectProperty $_ 'Ready') -and [bool](Get-ObjectProperty $_ 'Fixed')
    })
    if ($valid.Count -eq 0) { throw "volume '$Label' is missing" }
    if ($valid.Count -ne 1) { throw "volume '$Label' is ambiguous ($($valid.Count) matching volumes)" }
    $root = [string](Get-ObjectProperty $valid[0] 'Root')
    $volumeId = [string](Get-ObjectProperty $valid[0] 'VolumeId')
    if ([string]::IsNullOrWhiteSpace($root) -or [string]::IsNullOrWhiteSpace($volumeId)) { throw "volume '$Label' has no unique identity" }
    return [IO.Path]::GetFullPath($root)
}

function Assert-DistinctVolumes {
    param([string] $InputRoot, [string] $EvidenceRoot)
    $inputVolume = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($InputRoot))
    $evidenceVolume = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($EvidenceRoot))
    if ([string]::IsNullOrWhiteSpace($inputVolume) -or [string]::IsNullOrWhiteSpace($evidenceVolume)) { throw 'volume roots are unavailable' }
    if ([string]::Equals($inputVolume, $evidenceVolume, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'input and evidence must be distinct volumes'
    }
}

function Wait-ForRunVolumes {
    while ($true) {
        try {
            $inputRoot = Resolve-UniqueVolume -Label $script:InputLabel
            $evidenceRoot = Resolve-UniqueVolume -Label $script:EvidenceLabel
            Assert-DistinctVolumes $inputRoot $evidenceRoot
            return [ordered]@{ InputRoot = $inputRoot; EvidenceRoot = $evidenceRoot }
        } catch {
            Write-Host "waiting for one unique '$script:InputLabel' and '$script:EvidenceLabel' volume pair"
            Start-Sleep -Seconds $script:PollSeconds
        }
    }
}

function Get-TreeDigest {
    param([string] $Root)
    $rootItem = Assert-ExistingPathChain $Root 'input volume root'
    if (-not $rootItem.PSIsContainer) { throw 'input volume root must be a directory' }
    $rootPath = $rootItem.FullName.TrimEnd('\')
    $prefix = $rootPath + '\'
    $entries = New-Object 'System.Collections.Generic.List[string]'
    $pending = New-Object 'System.Collections.Generic.Stack[string]'
    $pending.Push($rootPath)
    $fileCount = 0
    while ($pending.Count -gt 0) {
        $directory = $pending.Pop()
        foreach ($item in @(Get-ChildItem -LiteralPath $directory -Force -ErrorAction Stop)) {
            if ([string]::Equals($directory, $rootPath, [StringComparison]::OrdinalIgnoreCase) -and (Test-ReservedVolumeRootName $item.Name)) { continue }
            try { $attributes = $item.Attributes } catch { throw "input entry metadata is unreadable: $($item.FullName): $($_.Exception.Message)" }
            if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "input contains reparse point: $($item.FullName)" }
            if ($item -is [IO.DirectoryInfo]) { $pending.Push($item.FullName); continue }
            if ($item -is [IO.FileInfo]) {
                $fileCount++
                if ($fileCount -gt $script:MaxInputFiles) { throw 'input file count bound exceeded' }
                if ($item.Length -gt $script:MaxFileBytes) { throw "input file is too large: $($item.Name)" }
                $relative = $item.FullName.Substring($prefix.Length).Replace('\', '/')
                $entries.Add("$relative|$($item.Length)|$(Get-Sha256 $item.FullName)")
                continue
            }
            throw "input entry has an unsupported identity: $($item.FullName)"
        }
    }
    $canonical = (($entries | Sort-Object) -join "`n") + "`n"
    $bytes = [Text.Encoding]::UTF8.GetBytes($canonical)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant() } finally { $sha.Dispose() }
}

function Read-JsonFile {
    param([string] $Path, [string] $Label)
    Assert-ExistingPathChain $Path $Label $true | Out-Null
    try { return ([IO.File]::ReadAllText($Path, [Text.Encoding]::UTF8) | ConvertFrom-Json -ErrorAction Stop) } catch { throw "$Label is not valid JSON: $($_.Exception.Message)" }
}

function Assert-RunContract {
    param([string] $InputRoot, [string] $EvidenceRoot)
    $runnerPath = Join-Path $InputRoot $script:RunnerName
    $scenarioPath = Join-Path $InputRoot $script:ScenarioName
    $expectedRunnerPath = Join-Path $InputRoot $script:ExpectedRunnerName
    $artifactManifestPath = Join-Path $InputRoot $script:ExpectedArtifactsName
    $runnerItem = Assert-ExistingPathChain $runnerPath 'runner.ps1' $true
    if ($runnerItem.Extension -ine '.ps1') { throw 'runner.ps1 must be a PowerShell script' }
    $scenario = Read-JsonFile $scenarioPath 'scenario.json'
    if ((Get-ObjectProperty $scenario 'schema') -ne $script:RunSchema) { throw 'scenario.json schema mismatch' }
    $scenarioId = [string](Get-ObjectProperty $scenario 'scenario')
    if ($scenarioId -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$') { throw 'scenario.json scenario is unsafe or missing' }
    Assert-ExistingPathChain $expectedRunnerPath 'expected-runner.sha256' $true | Out-Null
    $expectedText = [IO.File]::ReadAllText($expectedRunnerPath, [Text.Encoding]::UTF8).Trim()
    if ($expectedText -notmatch '^[0-9a-fA-F]{64}$') { throw 'expected-runner.sha256 is missing or malformed' }
    $runnerHash = Get-Sha256 $runnerPath
    if (-not [string]::Equals($runnerHash, $expectedText, [StringComparison]::OrdinalIgnoreCase)) { throw 'runner.ps1 hash mismatch' }
    $manifest = Read-JsonFile $artifactManifestPath 'expected-artifacts.json'
    if ((Get-ObjectProperty $manifest 'schema') -ne $script:ArtifactSchema) { throw 'expected-artifacts.json schema mismatch' }
    $artifacts = @(Get-ObjectProperty $manifest 'artifacts')
    if ($artifacts.Count -gt $script:MaxArtifacts) { throw 'artifact manifest bound exceeded' }
    $seen = @{}
    foreach ($artifact in $artifacts) {
        $relative = Assert-RelativePath ([string](Get-ObjectProperty $artifact 'path')) 'artifact path'
        $key = $relative.ToLowerInvariant()
        if ($seen.ContainsKey($key)) { throw "artifact path is duplicated: $relative" }
        $seen[$key] = $true
        $size = Get-ObjectProperty $artifact 'size'
        $hash = [string](Get-ObjectProperty $artifact 'sha256')
        if ($null -eq $size -or [int64]$size -lt 0 -or [int64]$size -gt $script:MaxFileBytes -or $hash -notmatch '^[0-9a-fA-F]{64}$') { throw "artifact manifest entry is malformed: $relative" }
    }
    return [ordered]@{
        RunnerPath = $runnerPath
        ScenarioPath = $scenarioPath
        Scenario = $scenarioId
        RunnerHash = $runnerHash
        ArtifactManifestPath = $artifactManifestPath
        ArtifactManifest = $manifest
    }
}

if (-not ('S11B.BoundedRunner' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace S11B {
    public static class BoundedRunner {
        private sealed class CopyState {
            public string Error = "";
        }

        private static void CopyBounded(Stream input, string path, int maxBytes, CopyState state) {
            try {
                using (var output = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read)) {
                    var buffer = new byte[8192];
                    long written = 0;
                    int count;
                    while ((count = input.Read(buffer, 0, buffer.Length)) > 0) {
                        if (written < maxBytes) {
                            var allowed = (int)Math.Min((long)count, maxBytes - written);
                            output.Write(buffer, 0, allowed);
                            written += allowed;
                        }
                    }
                    output.Flush();
                }
            } catch (Exception ex) {
                state.Error = ex.Message;
            }
        }

        private static string QuoteArgument(string value) {
            var builder = new StringBuilder();
            builder.Append('"');
            var slashes = 0;
            foreach (var character in value) {
                if (character == '\\') { slashes++; continue; }
                if (character == '"') {
                    builder.Append(new string('\\', slashes * 2 + 1));
                    builder.Append('"');
                    slashes = 0;
                    continue;
                }
                builder.Append(new string('\\', slashes));
                builder.Append(character);
                slashes = 0;
            }
            builder.Append(new string('\\', slashes * 2));
            builder.Append('"');
            return builder.ToString();
        }

        public static int Run(string engine, string runner, string scenario, string evidence, string stdout, string stderr, int timeoutSeconds, int maxBytes) {
            using (var process = new Process()) {
                var info = process.StartInfo;
                info.FileName = engine;
                info.Arguments = QuoteArgument("-NoProfile") + " " + QuoteArgument("-NonInteractive") + " " + QuoteArgument("-ExecutionPolicy") + " " + QuoteArgument("Bypass") + " " + QuoteArgument("-File") + " " + QuoteArgument(runner) + " " + QuoteArgument("-EvidenceRoot") + " " + QuoteArgument(evidence) + " " + QuoteArgument("-ScenarioPath") + " " + QuoteArgument(scenario);
                info.WorkingDirectory = Path.GetDirectoryName(runner);
                info.UseShellExecute = false;
                info.CreateNoWindow = true;
                info.RedirectStandardOutput = true;
                info.RedirectStandardError = true;
                if (!process.Start()) { throw new InvalidOperationException("runner process did not start"); }

                var stdoutState = new CopyState();
                var stderrState = new CopyState();
                var stdoutTask = Task.Factory.StartNew(() => CopyBounded(process.StandardOutput.BaseStream, stdout, maxBytes, stdoutState), TaskCreationOptions.LongRunning);
                var stderrTask = Task.Factory.StartNew(() => CopyBounded(process.StandardError.BaseStream, stderr, maxBytes, stderrState), TaskCreationOptions.LongRunning);
                var finished = process.WaitForExit(timeoutSeconds * 1000);
                if (!finished) {
                    try {
                        if (!process.HasExited) { process.Kill(); }
                    } catch (Exception ex) {
                        throw new InvalidOperationException("runner timeout kill failed: " + ex.Message, ex);
                    }
                    process.WaitForExit(5000);
                    Task.WaitAll(new[] { stdoutTask, stderrTask }, 5000);
                    return 124;
                }
                process.WaitForExit();
                Task.WaitAll(new[] { stdoutTask, stderrTask }, 5000);
                if (!String.IsNullOrEmpty(stdoutState.Error)) { throw new IOException("stdout capture failed: " + stdoutState.Error); }
                if (!String.IsNullOrEmpty(stderrState.Error)) { throw new IOException("stderr capture failed: " + stderrState.Error); }
                return process.ExitCode;
            }
        }
    }
}
'@
}

function Invoke-Runner {
    param(
        [string] $RunnerPath,
        [string] $ScenarioPath,
        [string] $EvidenceRoot,
        [string] $StdoutPath,
        [string] $StderrPath,
        [ValidateRange(1, 86400)]
        [int] $TimeoutSeconds = 300
    )
    $engineCommand = Get-Command powershell.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    $engine = if ($null -eq $engineCommand) { $null } else { [string]$engineCommand.Source }
    if ([string]::IsNullOrWhiteSpace($engine)) {
        $engineCommand = Get-Command pwsh.exe -ErrorAction SilentlyContinue | Select-Object -First 1
        $engine = if ($null -eq $engineCommand) { $null } else { [string]$engineCommand.Source }
    }
    if ([string]::IsNullOrWhiteSpace($engine)) { throw 'PowerShell runner engine is unavailable' }
    return [S11B.BoundedRunner]::Run($engine, $RunnerPath, $ScenarioPath, $EvidenceRoot, $StdoutPath, $StderrPath, $TimeoutSeconds, $script:MaxRunnerOutputChars)
}

function Assert-ExpectedArtifacts {
    param($Manifest, [string] $EvidenceRoot)
    $records = @()
    foreach ($artifact in @(Get-ObjectProperty $Manifest 'artifacts')) {
        $relative = Assert-RelativePath ([string](Get-ObjectProperty $artifact 'path')) 'artifact path'
        $path = Join-Path $EvidenceRoot $relative
        Assert-ExistingPathChain $path "artifact '$relative'" $true | Out-Null
        $item = Get-Item -LiteralPath $path -ErrorAction Stop
        $expectedSize = [int64](Get-ObjectProperty $artifact 'size')
        $expectedHash = [string](Get-ObjectProperty $artifact 'sha256').ToLowerInvariant()
        $actualHash = Get-Sha256 $path
        if ([int64]$item.Length -ne $expectedSize -or $actualHash -ne $expectedHash) { throw "artifact hash or size mismatch: $relative" }
        $records += [ordered]@{ path = $relative; size = [int64]$item.Length; sha256 = $actualHash }
    }
    return $records
}

function Write-FailureEvidence {
    param([string] $EvidenceRoot, [string] $Scenario, [Nullable[int]] $RunnerExitCode, [string] $Failure)
    $logPath = Join-Path $EvidenceRoot $script:LogName
    Write-BoundedLog $logPath $Failure 'ERROR'
    $donePath = Join-Path $EvidenceRoot $script:DoneName
    $exitPath = Join-Path $EvidenceRoot $script:ExitName
    $failureCode = if ($null -eq $RunnerExitCode) { -1 } else { [int]$RunnerExitCode }
    $done = [ordered]@{ schema = $script:DoneSchema; scenario = $Scenario; result = 'failed'; runnerExitCode = $failureCode; failure = $Failure; shutdownRequested = $false }
    $exit = [ordered]@{ schema = $script:ExitSchema; scenario = $Scenario; success = $false; exitCode = $failureCode; runnerExitCode = $failureCode; failure = $Failure; shutdownRequested = $false }
    try { if (-not (Test-Path -LiteralPath $donePath)) { Write-ExclusiveJson $donePath $done } } catch { }
    try { if (-not (Test-Path -LiteralPath $exitPath)) { Write-ExclusiveJson $exitPath $exit } } catch { }
}

function Invoke-BootstrapCycle {
    param([switch] $NoShutdown)
    $inputRoot = $null
    $evidenceRoot = $null
    $scenarioId = 'unknown'
    $runnerExitCode = $null
    $bootstrapHash = $null
    try {
        $volumes = Wait-ForRunVolumes
        $inputRoot = [string]$volumes.InputRoot
        $evidenceRoot = [string]$volumes.EvidenceRoot
        Assert-ExistingPathChain $inputRoot 'input volume root' | Out-Null
        Assert-ExistingPathChain $evidenceRoot 'evidence volume root' | Out-Null
        $contract = Assert-RunContract $inputRoot $evidenceRoot
        $scenarioId = $contract.Scenario
        $logPath = Join-Path $evidenceRoot $script:LogName
        Write-BoundedLog $logPath "starting scenario '$scenarioId'"
        $bootstrapHash = Get-BootstrapSha256
        Write-BoundedLog $logPath "bootstrap watcher sha256=$bootstrapHash"
        $beforeDigest = Get-TreeDigest $inputRoot
        $stdoutPath = Join-Path $evidenceRoot 'runner.stdout.txt'
        $stderrPath = Join-Path $evidenceRoot 'runner.stderr.txt'
        $runnerExitCode = Invoke-Runner $contract.RunnerPath $contract.ScenarioPath $evidenceRoot $stdoutPath $stderrPath $script:RunnerTimeoutSeconds
        $afterDigest = Get-TreeDigest $inputRoot
        if ($beforeDigest -ne $afterDigest) { throw 'input volume changed during runner execution' }
        if ($runnerExitCode -ne 0) { throw "runner exited with non-zero code $runnerExitCode" }
        $artifactRecords = @(Assert-ExpectedArtifacts $contract.ArtifactManifest $evidenceRoot)
        $done = [ordered]@{ schema = $script:DoneSchema; scenario = $scenarioId; result = 'success'; runnerExitCode = 0; runnerSha256 = $contract.RunnerHash; bootstrapSha256 = $bootstrapHash; inputTreeSha256 = $beforeDigest; inputUnchanged = $true; artifacts = $artifactRecords; shutdownRequested = (-not $NoShutdown) }
        $exit = [ordered]@{ schema = $script:ExitSchema; scenario = $scenarioId; success = $true; exitCode = 0; runnerExitCode = 0; failure = $null; shutdownRequested = (-not $NoShutdown) }
        Write-ExclusiveJson (Join-Path $evidenceRoot $script:DoneName) $done
        Write-BoundedLog $logPath "scenario '$scenarioId' completed with runner exit 0"
        Write-ExclusiveJson (Join-Path $evidenceRoot $script:ExitName) $exit
        if (-not $NoShutdown) { Stop-Computer -ComputerName 'localhost' -Confirm:$false }
        return $true
    } catch {
        $message = $_.Exception.Message
        if ($null -ne $evidenceRoot -and (Test-Path -LiteralPath $evidenceRoot)) { Write-FailureEvidence $evidenceRoot $scenarioId $runnerExitCode $message }
        throw
    }
}

if ($NoRun) { return }

while ($true) {
    try {
        Invoke-BootstrapCycle -NoShutdown:$NoShutdown | Out-Null
        if ($Once) { exit 0 }
    } catch {
        Write-Error $_.Exception.Message
        exit 1
    }
    Start-Sleep -Seconds $PollSeconds
}
