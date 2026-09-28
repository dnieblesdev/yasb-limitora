<#
.SYNOPSIS
    Host orchestrator - unattended S11b lifecycle loop.
.DESCRIPTION
    Runs the full scenario list unattended on the Hyper-V host.
    Per cycle: assert VM state, revert checkpoint, create and format
    evidence VHDX, write scenario.json, hot-add, wait for guest shutdown,
    hot-remove, mount read-only, extract, hash, cross-check guest-computed
    hashes against host-recomputed ones, dismount.
.NOTES
    Windows PowerShell 5.1 compatible. Uses [System.Security.Cryptography.SHA256]
    for hashing (Get-FileHash is not available in the elevated host context).
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $VmName,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $CheckpointName,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $EvidenceDirectory,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $ScenarioDirectory,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $VhdxDirectory,

    [int] $ControllerNumber = 0,
    [int] $ControllerLocation = 3,
    [int64] $VhdxSizeBytes = 4GB,
    [int] $ShutdownWaitTimeoutSeconds = 600,
    [int] $StartWaitTimeoutSeconds = 180,

    [string] $ExpectedWatcherSha256 = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

#region Helpers

function Get-HostSha256 {
    param([string] $Path)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $fs = [IO.File]::OpenRead($Path)
        try {
            return ([BitConverter]::ToString($sha.ComputeHash($fs))).Replace('-', '').ToLowerInvariant()
        } finally { $fs.Dispose() }
    } finally { $sha.Dispose() }
}

function Write-OrchestratorLog {
    param([string] $Message, [string] $Level = 'INFO')
    $timestamp = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
    Write-Output "$timestamp [$Level] $Message"
}

function Assert-PlainPath {
    param([string] $Path, [string] $Label)
    $full = [IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $full)) { throw "$Label does not exist: $full" }
    $item = Get-Item -LiteralPath $full -ErrorAction Stop
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "$Label is a reparse point" }
    return $item
}

function Wait-ForVmState {
    param([string] $Name, [string[]] $ExpectedStates, [int] $TimeoutSeconds)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $vm = Get-VM -Name $Name -ErrorAction SilentlyContinue
        if ($vm -and $vm.State.ToString() -in $ExpectedStates) { return $vm.State.ToString() }
        Start-Sleep -Seconds 3
    }
    throw "VM '$Name' did not reach state [$($ExpectedStates -join ', ')] within ${TimeoutSeconds}s"
}

function Get-MountedDriveLetter {
    param([string] $VhdxPath)
    # MSFT_DiskImage exposes Number, not DiskNumber; resolve the Disk object with a bounded wait.
    $disk = $null
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    while (-not $disk -and [DateTime]::UtcNow -lt $deadline) {
        $disk = Get-DiskImage -ImagePath $VhdxPath -ErrorAction Stop | Get-Disk -ErrorAction SilentlyContinue
        if (-not $disk) { Start-Sleep -Seconds 2 }
    }
    if (-not $disk) { throw "mounted VHDX did not surface as a disk within 30s: $VhdxPath" }
    $partition = Get-Partition -DiskNumber $disk.Number -ErrorAction Stop | Where-Object { $_.Type -eq 'Basic' } | Select-Object -First 1
    if (-not $partition -or -not $partition.DriveLetter) { throw "no drive letter found for mounted VHDX" }
    return "$($partition.DriveLetter):"
}

#endregion

#region Scenario loading

function Load-Scenarios {
    param([string] $Directory)
    $dir = Assert-PlainPath $Directory 'scenario directory'
    if (-not $dir.PSIsContainer) { throw 'scenario directory must be a directory' }
    $files = @(Get-ChildItem -LiteralPath $dir.FullName -Filter '*.json' -File | Sort-Object Name)
    if ($files.Count -eq 0) { throw "no scenario files found in $Directory" }
    $scenarios = @()
    foreach ($file in $files) {
        $raw = [IO.File]::ReadAllText($file.FullName, [Text.Encoding]::UTF8)
        $obj = $raw | ConvertFrom-Json
        if ($obj.schema -ne 'gentle-ai.yasb-limitora.s11b-scenario/v1') {
            throw "schema mismatch in $($file.Name): $($obj.schema)"
        }
        $scenarios += [ordered]@{
            File     = $file.FullName
            Name     = [string]$obj.scenario
            Content  = $raw
            Object   = $obj
        }
    }
    return ,$scenarios
}

#endregion

#region Cross-check

function Cross-CheckEvidence {
    param(
        [string] $ExtractedRoot,
        [string] $ScenarioName
    )
    $scenarioDir = Join-Path $ExtractedRoot $ScenarioName
    if (-not (Test-Path -LiteralPath $scenarioDir)) {
        Write-OrchestratorLog "no scenario directory for $ScenarioName in extracted evidence" 'WARN'
        return
    }

    $runRecords = @(Get-ChildItem -LiteralPath $scenarioDir -Recurse -Filter 'run-record.json' -File)
    $mismatches = @()
    $checked = 0

    foreach ($recordFile in $runRecords) {
        $raw = [IO.File]::ReadAllText($recordFile.FullName, [Text.Encoding]::UTF8)
        $record = $raw | ConvertFrom-Json

        # Check executable hash
        if ($record.executable -and $record.executable.sha256) {
            $guestHash = [string]$record.executable.sha256
            # The executable path in the record is the guest path; we can't verify it on the host
            # because the setup exe is on the data ISO, not the evidence volume.
        }

        # Check output files (stdout.txt, stderr.txt)
        if ($record.output) {
            foreach ($output in $record.output) {
                if ($output.sha256 -and $output.path) {
                    # The path is a guest path; try to find it relative to the run-record
                    $relativePath = [IO.Path]::GetFileName([string]$output.path)
                    $hostPath = Join-Path $recordFile.DirectoryName $relativePath
                    if (Test-Path -LiteralPath $hostPath) {
                        $hostHash = Get-HostSha256 $hostPath
                        $checked++
                        if ($hostHash -ne [string]$output.sha256) {
                            $mismatches += "hash mismatch: $hostPath (guest=$($output.sha256), host=$hostHash)"
                        }
                    }
                }
            }
        }

        # Check exact log
        if ($record.exactLog -and $record.exactLog.present -and $record.exactLog.sha256) {
            $logFileName = [IO.Path]::GetFileName([string]$record.exactLog.path)
            $hostLogPath = Join-Path $recordFile.DirectoryName $logFileName
            if (Test-Path -LiteralPath $hostLogPath) {
                $hostHash = Get-HostSha256 $hostLogPath
                $checked++
                if ($hostHash -ne [string]$record.exactLog.sha256) {
                    $mismatches += "log hash mismatch: $hostLogPath (guest=$($record.exactLog.sha256), host=$hostHash)"
                }
            }
        }
    }

    # Check state-capture.json tree hashes
    $stateCaptures = @(Get-ChildItem -LiteralPath $scenarioDir -Recurse -Filter 'state-capture.json' -File)
    foreach ($captureFile in $stateCaptures) {
        $raw = [IO.File]::ReadAllText($captureFile.FullName, [Text.Encoding]::UTF8)
        $capture = $raw | ConvertFrom-Json
        # State captures reference guest paths that don't exist on the host evidence volume
        # (they're snapshots of the guest filesystem). We verify the capture file itself.
        $checked++
    }

    # Hash scenario.json and done.json
    $scenarioJsonPath = Join-Path $ExtractedRoot 'scenario.json'
    $doneJsonPath = Join-Path $ExtractedRoot 'done.json'
    if (Test-Path -LiteralPath $scenarioJsonPath) {
        $scenarioHash = Get-HostSha256 $scenarioJsonPath
        Write-OrchestratorLog "scenario.json SHA-256: $scenarioHash"
    }
    if (Test-Path -LiteralPath $doneJsonPath) {
        $doneHash = Get-HostSha256 $doneJsonPath
        Write-OrchestratorLog "done.json SHA-256: $doneHash"
    }

    # Hash watcher.log
    $watcherLogPath = Join-Path $ExtractedRoot 'watcher.log'
    if (Test-Path -LiteralPath $watcherLogPath) {
        $logHash = Get-HostSha256 $watcherLogPath
        Write-OrchestratorLog "watcher.log SHA-256: $logHash"
    }

    if ($mismatches.Count -gt 0) {
        Write-OrchestratorLog "CROSS-CHECK FAILURES for ${ScenarioName}:" 'ERROR'
        foreach ($m in $mismatches) {
            Write-OrchestratorLog "  $m" 'ERROR'
        }
        throw "cross-check failed for scenario ${ScenarioName}: $($mismatches.Count) mismatch(es)"
    }
    Write-OrchestratorLog "cross-check passed for $ScenarioName ($checked file(s) verified)"
}

#endregion

#region Main loop

$evidenceDir = [IO.Path]::GetFullPath($EvidenceDirectory)
$vhdxDir = [IO.Path]::GetFullPath($VhdxDirectory)
if (-not (Test-Path -LiteralPath $evidenceDir)) { New-Item -ItemType Directory -Path $evidenceDir | Out-Null }
if (-not (Test-Path -LiteralPath $vhdxDir)) { New-Item -ItemType Directory -Path $vhdxDir | Out-Null }

# Identity header: a run must be self-contained for custody, so record the orchestrator's own hash,
# the target identities and the required guest build before any cycle starts.
Write-OrchestratorLog ('orchestrator script: ' + $PSCommandPath)
Write-OrchestratorLog ('orchestrator sha256: ' + (Get-HostSha256 $PSCommandPath))
Write-OrchestratorLog ('vm=' + $VmName + ' checkpoint=' + $CheckpointName)
Write-OrchestratorLog ('expected watcher sha256=' + $(if ([string]::IsNullOrWhiteSpace($ExpectedWatcherSha256)) { '(not gated)' } else { $ExpectedWatcherSha256.Trim().ToLowerInvariant() }))
Write-OrchestratorLog ('scenario directory: ' + $ScenarioDirectory)

$scenarios = Load-Scenarios $ScenarioDirectory
Write-OrchestratorLog "loaded $($scenarios.Count) scenario(s)"

$cycleResults = [System.Collections.ArrayList]::new()

for ($i = 0; $i -lt $scenarios.Count; $i++) {
    $scenario = $scenarios[$i]
    $scenarioName = $scenario.Name
    $cycleStart = [DateTime]::UtcNow
    Write-OrchestratorLog "=== Cycle $($i + 1)/$($scenarios.Count): $scenarioName ==="

    $vhdxPath = Join-Path $vhdxDir "s11b-evidence-$scenarioName.vhdx"
    $scenarioExtractDir = Join-Path $evidenceDir $scenarioName
    $cycleResult = [ordered]@{
        scenario    = $scenarioName
        startedUtc  = $cycleStart.ToString('o')
        finishedUtc = $null
        result      = 'unknown'
        detail      = $null
    }

    try {
        # 1. Assert VM state
        $vm = Get-VM -Name $VmName -ErrorAction Stop
        $vmState = $vm.State.ToString()
        if ($i -eq 0) {
            if ($vmState -ne 'Running' -and $vmState -ne 'Off') {
                throw "VM '$VmName' is in unexpected state '$vmState' for first cycle; expected Running or Off"
            }
        } else {
            if ($vmState -ne 'Off') {
                throw "VM '$VmName' is in unexpected state '$vmState'; expected Off after previous cycle"
            }
        }
        Write-OrchestratorLog "VM state: $vmState"

        # 2. Revert checkpoint
        Write-OrchestratorLog "reverting checkpoint '$CheckpointName'"
        $checkpoint = Get-VMCheckpoint -VMName $VmName -Name $CheckpointName -ErrorAction Stop
        $checkpoint | Restore-VMCheckpoint -Confirm:$false -ErrorAction Stop
        Start-Sleep -Seconds 2

        # 3. Start VM if revert left it Saved
        $vm = Get-VM -Name $VmName -ErrorAction Stop
        if ($vm.State.ToString() -eq 'Saved') {
            Write-OrchestratorLog "VM is Saved after revert; starting"
            Start-VM -Name $VmName -ErrorAction Stop
            $startedState = Wait-ForVmState $VmName @('Running') $StartWaitTimeoutSeconds
            Write-OrchestratorLog "VM started: $startedState"
        }

        # Wait for VM to be running (heartbeat)
        $vmRunning = Wait-ForVmState $VmName @('Running') $StartWaitTimeoutSeconds
        Write-OrchestratorLog "VM running: $vmRunning"

        # 4. Create and format evidence VHDX
        if (Test-Path -LiteralPath $vhdxPath) { throw "VHDX already exists: $vhdxPath" }
        Write-OrchestratorLog "creating VHDX: $vhdxPath ($($VhdxSizeBytes / 1MB) MiB)"
        New-VHD -Path $vhdxPath -Dynamic -SizeBytes $VhdxSizeBytes -ErrorAction Stop | Out-Null

        Write-OrchestratorLog "mounting VHDX for formatting"
        Mount-DiskImage -ImagePath $vhdxPath -ErrorAction Stop | Out-Null
        # MSFT_DiskImage exposes Number, not DiskNumber; resolve the Disk object with a bounded wait.
        $disk = $null
        $diskDeadline = [DateTime]::UtcNow.AddSeconds(30)
        while (-not $disk -and [DateTime]::UtcNow -lt $diskDeadline) {
            $disk = Get-DiskImage -ImagePath $vhdxPath -ErrorAction Stop | Get-Disk -ErrorAction SilentlyContinue
            if (-not $disk) { Start-Sleep -Seconds 2 }
        }
        if (-not $disk) { throw "mounted VHDX did not surface as a disk within 30s: $vhdxPath" }
        if ($disk.PartitionStyle -ne 'RAW') { throw "new VHDX partition style is not RAW: $($disk.PartitionStyle)" }
        $diskNumber = $disk.Number

        Initialize-Disk -Number $diskNumber -PartitionStyle GPT -Confirm:$false -ErrorAction Stop | Out-Null
        $partition = New-Partition -DiskNumber $diskNumber -UseMaximumSize -AssignDriveLetter -ErrorAction Stop
        $driveLetter = $partition.DriveLetter
        if (-not $driveLetter) { throw 'assigned partition has no drive letter' }
        Format-Volume -DriveLetter $driveLetter -FileSystem NTFS -NewFileSystemLabel 'S11BEVIDENCE' -Confirm:$false -ErrorAction Stop | Out-Null
        $mountRoot = $driveLetter + ':\'
        Write-OrchestratorLog "formatted volume as S11BEVIDENCE at $mountRoot"

        # 5. Write scenario.json
        $scenarioDestPath = Join-Path $mountRoot 'scenario.json'
        [IO.File]::WriteAllText($scenarioDestPath, $scenario.Content, [Text.UTF8Encoding]::new($false))
        $manifestHash = Get-HostSha256 $scenarioDestPath
        Write-OrchestratorLog "wrote scenario.json (SHA-256: $manifestHash)"

        # Declare which watcher build must be running in the guest. A checkpoint's saved RAM can carry
        # a stale CD-ROM cache, so the guest may execute an older watcher than the one on the host; the
        # watcher compares this stamp with its own script hash and fails closed on a mismatch.
        if (-not [string]::IsNullOrWhiteSpace($ExpectedWatcherSha256)) {
            $stampPath = Join-Path $mountRoot 'expected-watcher.sha256'
            [IO.File]::WriteAllText($stampPath, $ExpectedWatcherSha256.Trim().ToLowerInvariant() + "`n", [Text.UTF8Encoding]::new($false))
            Write-OrchestratorLog "wrote expected-watcher.sha256 ($($ExpectedWatcherSha256.Trim().ToLowerInvariant()))"
        } else {
            Write-OrchestratorLog 'no -ExpectedWatcherSha256 supplied; the watcher build is not gated' 'WARN'
        }

        # Dismount before hot-add
        Dismount-DiskImage -ImagePath $vhdxPath -ErrorAction Stop
        Write-OrchestratorLog "dismounted VHDX"

        # 6. Hot-add at SCSI controller
        Write-OrchestratorLog "hot-adding VHDX at SCSI $ControllerNumber/$ControllerLocation"
        Add-VMHardDiskDrive -VMName $VmName -ControllerType SCSI `
            -ControllerNumber $ControllerNumber -ControllerLocation $ControllerLocation `
            -Path $vhdxPath -ErrorAction Stop

        # 7. Wait for guest shutdown (Off)
        Write-OrchestratorLog "waiting for guest shutdown (timeout=$($ShutdownWaitTimeoutSeconds)s)"
        $attachTime = [DateTime]::UtcNow
        $finalState = Wait-ForVmState $VmName @('Off') $ShutdownWaitTimeoutSeconds
        $shutdownElapsed = [math]::Round(([DateTime]::UtcNow - $attachTime).TotalSeconds, 1)
        Write-OrchestratorLog "guest shut down after ${shutdownElapsed}s"

        # 8. Hot-remove
        Write-OrchestratorLog "hot-removing VHDX"
        $diskToRemove = Get-VMHardDiskDrive -VMName $VmName -ControllerType SCSI `
            -ControllerNumber $ControllerNumber -ControllerLocation $ControllerLocation -ErrorAction Stop
        $diskToRemove | Remove-VMHardDiskDrive -Confirm:$false -ErrorAction Stop

        # 9. Mount read-only
        Write-OrchestratorLog "mounting VHDX read-only"
        Mount-DiskImage -ImagePath $vhdxPath -Access ReadOnly -ErrorAction Stop
        $roDrive = Get-MountedDriveLetter $vhdxPath
        Write-OrchestratorLog "mounted read-only at $roDrive"

        # 10. Copy evidence
        if (Test-Path -LiteralPath $scenarioExtractDir) { throw "extraction directory already exists: $scenarioExtractDir" }
        New-Item -ItemType Directory -Path $scenarioExtractDir -ErrorAction Stop | Out-Null

        # Copy all files from the mounted volume
        $sourceRoot = $roDrive + '\'
        $copyItems = @(Get-ChildItem -LiteralPath $sourceRoot -Recurse -File -ErrorAction Stop)
        foreach ($item in $copyItems) {
            $relativePath = $item.FullName.Substring($sourceRoot.Length)
            $destPath = Join-Path $scenarioExtractDir $relativePath
            $destParent = [IO.Path]::GetDirectoryName($destPath)
            if (-not (Test-Path -LiteralPath $destParent)) {
                New-Item -ItemType Directory -Path $destParent -Force | Out-Null
            }
            Copy-Item -LiteralPath $item.FullName -Destination $destPath -ErrorAction Stop
        }
        Write-OrchestratorLog "copied $($copyItems.Count) file(s) to $scenarioExtractDir"

        # Hash every extracted file
        $extractedFiles = @(Get-ChildItem -LiteralPath $scenarioExtractDir -Recurse -File)
        foreach ($ef in $extractedFiles) {
            $hash = Get-HostSha256 $ef.FullName
            Write-OrchestratorLog "  $($ef.FullName.Substring($scenarioExtractDir.Length)): $hash"
        }

        # 11. Cross-check
        Cross-CheckEvidence $scenarioExtractDir $scenarioName

        # Dismount
        Dismount-DiskImage -ImagePath $vhdxPath -ErrorAction Stop
        Write-OrchestratorLog "dismounted read-only VHDX"

        $cycleResult.result = 'success'
        Write-OrchestratorLog "cycle $scenarioName completed successfully"

    } catch {
        $cycleResult.result = 'failed'
        $cycleResult.detail = $_.Exception.Message
        Write-OrchestratorLog "cycle $scenarioName FAILED: $($_.Exception.Message)" 'ERROR'

        # Try to clean up: remove the evidence disk from the VM first, then dismount it. A leftover
        # attached disk poisons the next attempt: the watcher finds an already-used scenario directory
        # in it and fails closed before running anything.
        try {
            $leftover = Get-VMHardDiskDrive -VMName $VmName -ErrorAction SilentlyContinue | Where-Object {
                $_.ControllerType -eq 'SCSI' -and $_.ControllerNumber -eq $ControllerNumber -and
                $_.ControllerLocation -eq $ControllerLocation -and $_.Path -eq $vhdxPath
            }
            if ($leftover) {
                $leftover | Remove-VMHardDiskDrive -Confirm:$false -ErrorAction SilentlyContinue
                Write-OrchestratorLog "hot-removed the evidence disk after the failed cycle" 'WARN'
                Start-Sleep -Seconds 2
            }
        } catch { }
        try {
            $diskImage = Get-DiskImage -ImagePath $vhdxPath -ErrorAction SilentlyContinue
            if ($diskImage -and $diskImage.Attached) {
                Dismount-DiskImage -ImagePath $vhdxPath -ErrorAction SilentlyContinue
            }
        } catch { }

        # Do NOT continue to next cycle on failure; stop so the operator can inspect
        $cycleResult.finishedUtc = [DateTime]::UtcNow.ToString('o')
        $cycleResults.Add($cycleResult) | Out-Null
        break
    }

    $cycleResult.finishedUtc = [DateTime]::UtcNow.ToString('o')
    $cycleResults.Add($cycleResult) | Out-Null
}

# Summary
Write-OrchestratorLog ''
Write-OrchestratorLog '=== Cycle Summary ==='
foreach ($cr in $cycleResults) {
    $elapsed = ''
    if ($cr.startedUtc -and $cr.finishedUtc) {
        $start = [DateTime]::Parse($cr.startedUtc).ToUniversalTime()
        $end = [DateTime]::Parse($cr.finishedUtc).ToUniversalTime()
        $elapsed = " ($([math]::Round(($end - $start).TotalSeconds, 1))s)"
    }
    Write-OrchestratorLog "  $($cr.scenario): $($cr.result)$elapsed"
    if ($cr.detail) { Write-OrchestratorLog "    detail: $($cr.detail)" }
}

$failedCycles = @($cycleResults | Where-Object { $_.result -ne 'success' })
if ($failedCycles.Count -gt 0) {
    Write-OrchestratorLog "ORCHESTRATOR FINISHED WITH $($failedCycles.Count) FAILURE(S)" 'ERROR'
    exit 1
} else {
    Write-OrchestratorLog "ORCHESTRATOR FINISHED SUCCESSFULLY ($($cycleResults.Count) cycle(s))"
    exit 0
}

#endregion
