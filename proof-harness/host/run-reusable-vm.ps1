<#
.SYNOPSIS
    Run one scenario-independent reusable checkpoint cycle.
.DESCRIPTION
    Restores exactly one generic logged-in checkpoint, hot-attaches fresh input and
    evidence VHDX volumes, waits for explicit guest completion plus VM Off, extracts
    evidence offline, and independently verifies runner/input/artifact/exit hashes.
    Windows PowerShell 5.1 does not provide a trustworthy -ReadOnly attachment
    contract on the observed host. The default is therefore fail-closed. The only
    executable mode is the explicit integrity-only fallback, which compares the
    complete input tree before and after the guest run and fails on any change.

    -DryRun validates the source contract and prints the planned operations without
    calling Hyper-V, disk, VM, or process-mutating cmdlets. -NoRun only dot-sources
    helper functions for harmless tests.
.NOTES
    Windows PowerShell 5.1 compatible. No DVD, ISO, cache, PowerShell Direct,
    Enhanced Session, KVP, clipboard, share, setup, or uninstaller operation is used.
    The checkpoint must already contain only the universal bootstrap watcher and OS
    state; scenario material is never frozen in it.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $VmName,
    [Parameter(Mandatory = $true)] [string] $CheckpointName,
    [Parameter(Mandatory = $true)] [string] $RunnerPath,
    [Parameter(Mandatory = $true)] [string] $ScenarioPath,
    [Parameter(Mandatory = $true)] [string] $ExpectedArtifactsPath,
    [Parameter(Mandatory = $true)] [string] $VhdxDirectory,
    [Parameter(Mandatory = $true)] [string] $EvidenceDirectory,
    [string[]] $AdditionalInputPath = @(),
    [string] $VerifierPath = '',
    [string] $BootstrapPath = '',
    [string] $PythonExe = 'python',
    [int] $InputControllerNumber = 0,
    [int] $InputControllerLocation = 3,
    [int] $EvidenceControllerNumber = 0,
    [int] $EvidenceControllerLocation = 4,
    [int] $WatchdogTimeoutSeconds = 600,
    [int64] $InputSizeBytes = 1GB,
    [int64] $EvidenceSizeBytes = 4GB,
    [switch] $AllowWritableInputIntegrityFallback,
    [switch] $DryRun,
    [switch] $NoRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:InputLabel = 'S11BINPUTS'
$script:EvidenceLabel = 'S11BEVIDENCE'
$script:ReservedVolumeRootNames = @('SYSTEM VOLUME INFORMATION', '$RECYCLE.BIN')
$script:InputVolumePath = $null
$script:EvidenceVolumePath = $null
$script:VmNameForCleanup = $null
if ([string]::IsNullOrWhiteSpace($VerifierPath) -and -not [string]::IsNullOrWhiteSpace($PSScriptRoot)) {
    $VerifierPath = Join-Path $PSScriptRoot 'verify-reusable-evidence.py'
}
if ([string]::IsNullOrWhiteSpace($BootstrapPath) -and -not [string]::IsNullOrWhiteSpace($PSScriptRoot)) {
    $BootstrapPath = Join-Path $PSScriptRoot '..\guest\bootstrap-watch.ps1'
}

function Test-ReservedVolumeRootName {
    param([string] $Name)
    return $script:ReservedVolumeRootNames -contains ([string]$Name).ToUpperInvariant()
}

function Get-HostSha256 {
    param([string] $Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $stream = [IO.File]::OpenRead($Path)
        try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
        finally { $stream.Dispose() }
    } finally { $sha.Dispose() }
}

function Assert-PlainDirectory {
    param([string] $Path, [string] $Label)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) { throw "$Label does not exist: $Path" }
    $item = Get-Item -LiteralPath $Path -ErrorAction Stop
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "$Label is a reparse point" }
    return $item
}

function Get-InputTreeDigest {
    param([string] $Root)
    $rootItem = Assert-PlainDirectory $Root 'input root'
    $rootPath = $rootItem.FullName.TrimEnd('\')
    $prefix = $rootPath + '\'
    $entries = New-Object 'System.Collections.Generic.List[string]'
    $pending = New-Object 'System.Collections.Generic.Stack[string]'
    $pending.Push($rootPath)
    while ($pending.Count -gt 0) {
        $directory = $pending.Pop()
        foreach ($item in @(Get-ChildItem -LiteralPath $directory -Force -ErrorAction Stop)) {
            if ([string]::Equals($directory, $rootPath, [StringComparison]::OrdinalIgnoreCase) -and (Test-ReservedVolumeRootName $item.Name)) { continue }
            try { $attributes = $item.Attributes } catch { throw "input entry metadata is unreadable: $($item.FullName): $($_.Exception.Message)" }
            if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "input contains a reparse point: $($item.FullName)" }
            if ($item -is [IO.DirectoryInfo]) { $pending.Push($item.FullName); continue }
            if ($item -is [IO.FileInfo]) {
                $relative = $item.FullName.Substring($prefix.Length).Replace('\', '/')
                $entries.Add("$relative|$($item.Length)|$(Get-HostSha256 $item.FullName)")
                continue
            }
            throw "input entry has an unsupported identity: $($item.FullName)"
        }
    }
    $canonical = (($entries | Sort-Object) -join "`n") + "`n"
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($canonical)))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}

function Wait-ForVmState {
    param([string] $Name, [string[]] $ExpectedStates, [int] $TimeoutSeconds)
    if ($TimeoutSeconds -lt 1) { throw 'timeout must be positive' }
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $vm = Get-VM -Name $Name -ErrorAction SilentlyContinue
        if ($vm -and ($ExpectedStates -contains $vm.State.ToString())) { return $vm.State.ToString() }
        Start-Sleep -Seconds 1
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "VM '$Name' did not reach [$($ExpectedStates -join ', ')] within ${TimeoutSeconds}s"
}

function Get-CheckpointIdentity {
    param([object] $CheckpointObject, [string] $RequestedName)
    if ($null -eq $CheckpointObject) { throw "generic checkpoint '$RequestedName' was not found" }
    $identity = [ordered]@{}
    foreach ($propertyName in @('Name', 'Id', 'VMId', 'CreationTime')) {
        $property = $CheckpointObject.PSObject.Properties[$propertyName]
        if ($null -eq $property -or $null -eq $property.Value) {
            throw "checkpoint '$RequestedName' is missing native identity property '$propertyName'"
        }
        if ($propertyName -eq 'CreationTime') {
            try { $value = ([DateTime]$property.Value).ToUniversalTime().ToString('o') }
            catch { throw "checkpoint '$RequestedName' has an invalid CreationTime" }
        } else {
            $value = ([string]$property.Value).Trim()
        }
        if ([string]::IsNullOrWhiteSpace($value)) { throw "checkpoint '$RequestedName' has an empty native identity property '$propertyName'" }
        $identity[$propertyName] = $value
    }
    if (-not [string]::Equals($identity['Name'], $RequestedName, [StringComparison]::Ordinal)) {
        throw "requested checkpoint name '$RequestedName' resolved to '$($identity['Name'])'"
    }
    return $identity
}

function Assert-SameCheckpointIdentity {
    param([System.Collections.IDictionary] $Before, [System.Collections.IDictionary] $After)
    foreach ($propertyName in @('Name', 'Id', 'VMId', 'CreationTime')) {
        if (-not [string]::Equals([string]$Before[$propertyName], [string]$After[$propertyName], [StringComparison]::Ordinal)) {
            throw "checkpoint identity drift for $propertyName (before=$($Before[$propertyName]) after=$($After[$propertyName]))"
        }
    }
}

function Restore-SameGenericCheckpoint {
    param([string] $Name, [string] $Checkpoint)
    $vm = Get-VM -Name $Name -ErrorAction Stop
    if ($vm.State.ToString() -notin @('Off', 'Saved', 'Running')) { throw "VM '$Name' is not restorable from state '$($vm.State)'" }
    $checkpointObject = Get-VMCheckpoint -VMName $Name -Name $Checkpoint -ErrorAction Stop
    $beforeIdentity = Get-CheckpointIdentity $checkpointObject $Checkpoint
    $checkpointObject | Restore-VMCheckpoint -Confirm:$false -ErrorAction Stop
    $afterObject = Get-VMCheckpoint -VMName $Name -Name $Checkpoint -ErrorAction Stop
    $afterIdentity = Get-CheckpointIdentity $afterObject $Checkpoint
    try { Assert-SameCheckpointIdentity $beforeIdentity $afterIdentity }
    catch {
        $drift = [InvalidOperationException]::new(('checkpoint identity drift: ' + $_.Exception.Message))
        $drift.Data['checkpointBeforeRestore'] = $beforeIdentity
        $drift.Data['checkpointAfterRestore'] = $afterIdentity
        throw $drift
    }
    $after = Get-VM -Name $Name -ErrorAction Stop
    if ($after.State.ToString() -in @('Off', 'Saved')) {
        Start-VM -Name $Name -ErrorAction Stop | Out-Null
    }
    Wait-ForVmState $Name @('Running') 120 | Out-Null
    return [pscustomobject]@{ Before = $beforeIdentity; After = $afterIdentity }
}

function Add-RunDisk {
    param([string] $Name, [string] $Path, [int] $ControllerNumber, [int] $ControllerLocation)
    $parameters = @{
        VMName = $Name
        ControllerType = 'SCSI'
        ControllerNumber = $ControllerNumber
        ControllerLocation = $ControllerLocation
        Path = $Path
        ErrorAction = 'Stop'
    }
    # Observed Windows PowerShell 5.1 has no trustworthy read-only attachment
    # parameter. This function intentionally attaches writable disks only; the
    # caller must have explicitly selected the integrity-only threat model.
    Add-VMHardDiskDrive @parameters | Out-Null
}

function Remove-RunDisk {
    param([string] $Name, [string] $Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return }
    $attached = @(Get-VMHardDiskDrive -VMName $Name -ErrorAction Stop | Where-Object { [string]::Equals([string]$_.Path, $Path, [StringComparison]::OrdinalIgnoreCase) })
    foreach ($disk in $attached) {
        $disk | Remove-VMHardDiskDrive -Confirm:$false -ErrorAction Stop
    }
}

function Invoke-DiskImageCleanup {
    param([string] $Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return }
    $image = Get-DiskImage -ImagePath $Path -ErrorAction Stop
    if ($image -and $image.Attached) { Dismount-DiskImage -ImagePath $Path -ErrorAction Stop | Out-Null }
}

function Get-MountedVolumeRoot {
    param([string] $Path, [int] $TimeoutSeconds = 30)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $disk = Get-DiskImage -ImagePath $Path -ErrorAction Stop | Get-Disk -ErrorAction SilentlyContinue
        if ($disk) {
            $partition = Get-Partition -DiskNumber $disk.Number -ErrorAction Stop | Where-Object { $_.DriveLetter } | Select-Object -First 1
            if ($partition) { return ([string]$partition.DriveLetter + ':\') }
        }
        Start-Sleep -Seconds 1
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "mounted VHDX has no accessible partition within ${TimeoutSeconds}s: $Path"
}

function Copy-PlainTree {
    param([string] $SourceRoot, [string] $DestinationRoot)
    $source = Assert-PlainDirectory $SourceRoot 'mounted volume'
    New-Item -ItemType Directory -Path $DestinationRoot -ErrorAction Stop | Out-Null
    $sourceRootPath = $source.FullName.TrimEnd('\')
    $pending = New-Object 'System.Collections.Generic.Stack[object]'
    $pending.Push([pscustomobject]@{ Source = $sourceRootPath; Destination = [IO.Path]::GetFullPath($DestinationRoot); IsRoot = $true })
    while ($pending.Count -gt 0) {
        $current = $pending.Pop()
        foreach ($item in @(Get-ChildItem -LiteralPath $current.Source -Force -ErrorAction Stop)) {
            if ($current.IsRoot -and (Test-ReservedVolumeRootName $item.Name)) { continue }
            try { $attributes = $item.Attributes } catch { throw "mounted evidence entry metadata is unreadable: $($item.FullName): $($_.Exception.Message)" }
            if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "mounted evidence contains a reparse point: $($item.FullName)" }
            $destination = Join-Path $current.Destination $item.Name
            if ($item -is [IO.DirectoryInfo]) {
                New-Item -ItemType Directory -Path $destination -Force -ErrorAction Stop | Out-Null
                $pending.Push([pscustomobject]@{ Source = $item.FullName; Destination = $destination; IsRoot = $false })
            } elseif ($item -is [IO.FileInfo]) {
                Copy-Item -LiteralPath $item.FullName -Destination $destination -ErrorAction Stop
            } else {
                throw "mounted evidence entry has an unsupported identity: $($item.FullName)"
            }
        }
    }
}

function Try-ExtractFailureEvidence {
    param([string] $Name, [string] $EvidenceVhdx, [string] $Archive)
    try {
        Remove-RunDisk $Name $EvidenceVhdx
        Mount-DiskImage -ImagePath $EvidenceVhdx -Access ReadOnly -ErrorAction Stop | Out-Null
        $root = Get-MountedVolumeRoot $EvidenceVhdx
        try { Copy-PlainTree $root (Join-Path $Archive 'evidence') }
        finally { Invoke-DiskImageCleanup $EvidenceVhdx }
        return $true
    } catch {
        Write-FailureRecord $Archive ('failure evidence extraction failed: ' + $_.Exception.Message) 'extraction'
        try { Invoke-DiskImageCleanup $EvidenceVhdx } catch { Write-Warning "failure evidence dismount failed: $($_.Exception.Message)" }
        return $false
    }
}

function New-UniqueRunDirectory {
    param([string] $Root, [string] $Prefix)
    if (-not (Test-Path -LiteralPath $Root)) { New-Item -ItemType Directory -Path $Root -ErrorAction Stop | Out-Null }
    for ($attempt = 0; $attempt -lt 5; $attempt++) {
        $name = $Prefix + '-' + [Guid]::NewGuid().ToString('N')
        $path = Join-Path $Root $name
        try { New-Item -ItemType Directory -Path $path -ErrorAction Stop | Out-Null; return $path } catch { }
    }
    throw "could not allocate a unique run archive under $Root"
}

function Invoke-OfflineEvidenceVerifier {
    param([string] $EvidenceRoot, [string] $InputRoot, [string] $ScriptPath, [string] $Python, [string] $ExpectedBootstrapSha256, [string] $HostProvenancePath)
    if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) { throw "offline verifier is missing: $ScriptPath" }
    if (-not (Test-Path -LiteralPath $HostProvenancePath -PathType Leaf)) { throw "host provenance is missing: $HostProvenancePath" }
    $output = & $Python $ScriptPath $EvidenceRoot '--input-root' $InputRoot '--expected-bootstrap-sha256' $ExpectedBootstrapSha256 '--host-provenance' $HostProvenancePath 2>&1
    $output | ForEach-Object { Write-Output $_ }
    if ($LASTEXITCODE -ne 0) { throw "offline evidence verification failed with exit code $LASTEXITCODE" }
}

function Write-HostRunProvenance {
    param([string] $Directory, [System.Collections.IDictionary] $Record)
    if ([string]::IsNullOrWhiteSpace($Directory)) { throw 'host provenance archive directory is missing' }
    if ($null -eq $Record) { throw 'host provenance record is missing' }
    try {
        $path = Join-Path $Directory 'host-provenance.json'
        $json = $Record | ConvertTo-Json -Depth 16
        [IO.File]::WriteAllText($path, $json + "`n", [Text.UTF8Encoding]::new($false))
    } catch {
        throw ('host provenance write failed: ' + $_.Exception.Message)
    }
}

function Write-FailureRecord {
    param([string] $Directory, [string] $Message, [string] $RunId)
    try {
        $record = [ordered]@{ schema = 'gentle-ai.yasb-limitora.reusable-vm-host-failure/v1'; runId = $RunId; failure = $Message; utc = [DateTime]::UtcNow.ToString('o') }
        [IO.File]::WriteAllText((Join-Path $Directory 'host-failure.json'), ($record | ConvertTo-Json -Depth 8) + "`n", [Text.UTF8Encoding]::new($false))
    } catch { Write-Warning "failed to write host failure record: $($_.Exception.Message)" }
}

function Write-CleanupFailure {
    param([string] $Directory, [string[]] $Failures, [string] $RunId)
    $record = [ordered]@{ schema = 'gentle-ai.yasb-limitora.reusable-vm-cleanup-failure/v1'; runId = $RunId; failures = @($Failures); utc = [DateTime]::UtcNow.ToString('o') }
    try {
        [IO.File]::WriteAllText((Join-Path $Directory 'cleanup-failure.json'), ($record | ConvertTo-Json -Depth 8) + "`n", [Text.UTF8Encoding]::new($false))
    } catch { Write-Warning "cleanup failure could not be recorded: $($_.Exception.Message)" }
}

function Invoke-ReusableRun {
    param(
        [string] $Name,
        [string] $Checkpoint,
        [string] $Runner,
        [string] $Scenario,
        [string] $ExpectedArtifacts,
        [string] $VhdxRoot,
        [string] $EvidenceRoot,
        [string[]] $OptionalPaths = @(),
        [string] $Verifier = $VerifierPath,
        [string] $Bootstrap = $BootstrapPath,
        [string] $Python = $PythonExe,
        [int] $WatchdogSeconds = 600,
        [int64] $InputBytes = 1GB,
        [int64] $EvidenceBytes = 4GB,
        [bool] $AllowWritableFallback = $false,
        [switch] $DryRun
    )
    Assert-PlainDirectory (Split-Path -Parent ([IO.Path]::GetFullPath($Runner))) 'runner parent' | Out-Null
    $runId = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '-' + [Guid]::NewGuid().ToString('N')
    $inputPath = Join-Path ([IO.Path]::GetFullPath($VhdxRoot)) ($runId + '-inputs.vhdx')
    $evidencePath = Join-Path ([IO.Path]::GetFullPath($VhdxRoot)) ($runId + '-evidence.vhdx')
    if (-not $DryRun -and -not $AllowWritableFallback) {
        throw 'true read-only input attachment is unavailable on the observed Windows PowerShell 5.1 host; pass -AllowWritableInputIntegrityFallback to opt into writable pre/post integrity checks'
    }
    if (-not $DryRun -and -not (Test-Path -LiteralPath $Bootstrap -PathType Leaf)) {
        throw "generic bootstrap watcher source is missing: $Bootstrap"
    }
    if (-not (Get-Command New-RunVolumes -CommandType Function -ErrorAction SilentlyContinue)) {
        $invokeDryRun = [bool]$DryRun
        . (Join-Path $PSScriptRoot 'new-run-volumes.ps1') -RunnerPath $Runner -ScenarioPath $Scenario `
            -ExpectedArtifactsPath $ExpectedArtifacts -InputVhdxPath $inputPath -EvidenceVhdxPath $evidencePath -NoRun
        # Dot-sourcing a PS1 shares the current scope; restore the caller's switch
        # so a dry-run cannot accidentally stage real VHDX files.
        $DryRun = $invokeDryRun
    }
    $volumePlan = New-RunVolumes -Runner $Runner -Scenario $Scenario -ExpectedArtifacts $ExpectedArtifacts `
        -InputPath $inputPath -EvidencePath $evidencePath -InputBytes $InputBytes -EvidenceBytes $EvidenceBytes `
        -OptionalPaths $OptionalPaths -DryRun:$DryRun
    $result = [ordered]@{ schema = 'gentle-ai.yasb-limitora.reusable-vm-host-run/v1'; runId = $runId; result = 'planned'; inputLabel = $script:InputLabel; evidenceLabel = $script:EvidenceLabel; readOnlyMode = 'unknown'; inputTreeSha256 = $null }
    if ($DryRun) {
        $result.operations = @('restore same generic checkpoint', 'attach writable S11BINPUTS only with explicit integrity fallback', 'attach S11BEVIDENCE writable', 'wait bounded for guest exit and VM Off', 'detach both disks on every outcome', 'extract evidence offline', 'cross-check hashes')
        return $result
    }

    $archive = $null
    $failure = $null
    $provenance = $null
    $attachedInput = $false
    $attachedEvidence = $false
    $script:VmNameForCleanup = $Name
    $script:InputVolumePath = $inputPath
    $script:EvidenceVolumePath = $evidencePath
    try {
        $archive = New-UniqueRunDirectory (Join-Path ([IO.Path]::GetFullPath($EvidenceRoot)) 'runs') ('run-' + $runId)
        $staged = $volumePlan
        $preInputDigest = [string]$staged.inputTreeSha256
        $expectedBootstrapSha256 = Get-HostSha256 $Bootstrap
        $provenance = [ordered]@{
            schema = 'gentle-ai.yasb-limitora.reusable-vm-host-provenance/v1'
            runId = $runId
            vmName = $Name
            requestedCheckpointName = $Checkpoint
            requestedCheckpointId = $null
            requestedCheckpointVmId = $null
            requestedCheckpointCreationTimeUtc = $null
            checkpointBeforeRestore = $null
            checkpointAfterRestore = $null
            restoreObservedUtc = $null
            bootstrapSha256 = $expectedBootstrapSha256
            runnerSha256 = [string]$staged.runnerSha256
            inputVhdxSha256 = $null
            outcomes = [ordered]@{
                checkpointRestore = 'pending'
                guestRun = 'pending'
                evidenceExtraction = 'pending'
                verification = 'pending'
                overall = 'pending'
            }
        }
        $provenance.inputVhdxSha256 = Get-HostSha256 $inputPath
        try {
            $restoreObservation = Restore-SameGenericCheckpoint $Name $Checkpoint
            $provenance.requestedCheckpointId = [string]$restoreObservation.Before['Id']
            $provenance.requestedCheckpointVmId = [string]$restoreObservation.Before['VMId']
            $provenance.requestedCheckpointCreationTimeUtc = [string]$restoreObservation.Before['CreationTime']
            $provenance.checkpointBeforeRestore = $restoreObservation.Before
            $provenance.checkpointAfterRestore = $restoreObservation.After
            $provenance.restoreObservedUtc = [DateTime]::UtcNow.ToString('o')
            $provenance.outcomes.checkpointRestore = 'success'
            Write-HostRunProvenance $archive $provenance
        } catch {
            if ($_.Exception.Data -and $_.Exception.Data['checkpointBeforeRestore']) {
                $provenance.checkpointBeforeRestore = $_.Exception.Data['checkpointBeforeRestore']
                $provenance.checkpointAfterRestore = $_.Exception.Data['checkpointAfterRestore']
                $provenance.requestedCheckpointId = [string]$provenance.checkpointBeforeRestore['Id']
                $provenance.requestedCheckpointVmId = [string]$provenance.checkpointBeforeRestore['VMId']
                $provenance.requestedCheckpointCreationTimeUtc = [string]$provenance.checkpointBeforeRestore['CreationTime']
            }
            $provenance.restoreObservedUtc = [DateTime]::UtcNow.ToString('o')
            $provenance.outcomes.checkpointRestore = 'failed'
            $provenance.outcomes.overall = 'failed'
            $provenance.failure = $_.Exception.Message
            Write-HostRunProvenance $archive $provenance
            throw
        }
        $result.readOnlyMode = 'writable-integrity-only'
        $result.inputThreatModel = 'A guest can transiently tamper with writable input and restore the original bytes before post-hash; pre/post hashing detects persistent mutation only.'
        Add-RunDisk $Name $inputPath $InputControllerNumber $InputControllerLocation
        $attachedInput = $true
        Add-RunDisk $Name $evidencePath $EvidenceControllerNumber $EvidenceControllerLocation
        $attachedEvidence = $true
        Wait-ForVmState $Name @('Off') $WatchdogSeconds | Out-Null
        Remove-RunDisk $Name $inputPath
        $attachedInput = $false
        Remove-RunDisk $Name $evidencePath
        $attachedEvidence = $false

        Mount-DiskImage -ImagePath $inputPath -Access ReadOnly -ErrorAction Stop | Out-Null
        $inputMount = Get-MountedVolumeRoot $inputPath
        try {
            $postInputDigest = Get-InputTreeDigest $inputMount
            $result.inputTreeSha256 = $postInputDigest
            if ($preInputDigest -ne $postInputDigest) { throw "input tree changed during guest run (before=$preInputDigest after=$postInputDigest)" }
            Copy-PlainTree $inputMount (Join-Path $archive 'input')
        } finally { Invoke-DiskImageCleanup $inputPath }

        Mount-DiskImage -ImagePath $evidencePath -Access ReadOnly -ErrorAction Stop | Out-Null
        $evidenceMount = Get-MountedVolumeRoot $evidencePath
        try { Copy-PlainTree $evidenceMount (Join-Path $archive 'evidence') }
        finally { Invoke-DiskImageCleanup $evidencePath }
        $provenance.outcomes.guestRun = 'success'
        $provenance.outcomes.evidenceExtraction = 'success'
        Invoke-OfflineEvidenceVerifier (Join-Path $archive 'evidence') (Join-Path $archive 'input') $Verifier $Python $expectedBootstrapSha256 (Join-Path $archive 'host-provenance.json')
        $exitPath = Join-Path $archive 'evidence\exit.json'
        if (-not (Test-Path -LiteralPath $exitPath -PathType Leaf)) { throw 'offline verifier returned without exit.json' }
        $result.exitSha256 = Get-HostSha256 $exitPath
        $provenance.outcomes.verification = 'success'
        $provenance.outcomes.overall = 'success'
        Write-HostRunProvenance $archive $provenance
        $result.result = 'success'
        return $result
    } catch {
        $failure = $_.Exception.Message
        if ($provenance) {
            $provenance.outcomes.overall = 'failed'
            $provenance.failure = $failure
            try { Write-HostRunProvenance $archive $provenance }
            catch { $failure = $_.Exception.Message }
        }
        if (-not $archive) { $archive = New-UniqueRunDirectory (Join-Path ([IO.Path]::GetFullPath($EvidenceRoot)) 'failed') ('failed-' + $runId) }
        Try-ExtractFailureEvidence $Name $evidencePath $archive | Out-Null
        Write-FailureRecord $archive $failure $runId
        throw $failure
    } finally {
        # Attempt both disks and both images independently; cleanup errors are
        # recorded rather than being reported as silent success.
        $cleanupFailures = @()
        foreach ($cleanup in @(
            [ordered]@{ Kind = 'input-disk'; Action = { Remove-RunDisk $Name $inputPath } },
            [ordered]@{ Kind = 'evidence-disk'; Action = { Remove-RunDisk $Name $evidencePath } },
            [ordered]@{ Kind = 'input-image'; Action = { Invoke-DiskImageCleanup $inputPath } },
            [ordered]@{ Kind = 'evidence-image'; Action = { Invoke-DiskImageCleanup $evidencePath } }
        )) {
            try { & $cleanup.Action } catch { $cleanupFailures += ($cleanup.Kind + ': ' + $_.Exception.Message) }
        }
        if ($cleanupFailures.Count -gt 0 -and $archive) {
            Write-CleanupFailure $archive $cleanupFailures $runId
            if (-not $failure) { throw ('cleanup failed: ' + ($cleanupFailures -join '; ')) }
            Write-Warning ('cleanup failed after run failure: ' + ($cleanupFailures -join '; '))
        }
        $script:InputVolumePath = $null
        $script:EvidenceVolumePath = $null
        $script:VmNameForCleanup = $null
    }
}

if (-not $NoRun) {
    $result = Invoke-ReusableRun -Name $VmName -Checkpoint $CheckpointName -Runner $RunnerPath -Scenario $ScenarioPath `
        -ExpectedArtifacts $ExpectedArtifactsPath -VhdxRoot $VhdxDirectory -EvidenceRoot $EvidenceDirectory `
        -OptionalPaths $AdditionalInputPath -Verifier $VerifierPath -Bootstrap $BootstrapPath -Python $PythonExe -WatchdogSeconds $WatchdogTimeoutSeconds `
        -InputBytes $InputSizeBytes -EvidenceBytes $EvidenceSizeBytes -AllowWritableFallback:$AllowWritableInputIntegrityFallback -DryRun:$DryRun
    $result | ConvertTo-Json -Depth 8
}
