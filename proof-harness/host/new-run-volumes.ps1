<#
.SYNOPSIS
    Stage one reusable-run input VHDX and one empty evidence VHDX.
.DESCRIPTION
    This versioned helper owns only per-run volume preparation. It writes the exact
    S11BINPUTS contract (runner.ps1, scenario.json, expected-runner.sha256,
    expected-artifacts.json, and explicitly declared optional payloads) and labels the
    second volume S11BEVIDENCE. -DryRun performs validation and emits a plan without
    calling Hyper-V or storage cmdlets.
.NOTES
    Windows PowerShell 5.1 compatible. The input volume is never changed after the
    staging phase by this helper. The observed Windows PowerShell 5.1 host does not
    provide a trustworthy guest read-only attachment contract, so the run orchestrator
    refuses execution unless its explicit writable integrity-only fallback is enabled.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $RunnerPath,
    [Parameter(Mandatory = $true)] [string] $ScenarioPath,
    [Parameter(Mandatory = $true)] [string] $ExpectedArtifactsPath,
    [Parameter(Mandatory = $true)] [string] $InputVhdxPath,
    [Parameter(Mandatory = $true)] [string] $EvidenceVhdxPath,
    [int64] $InputSizeBytes = 1GB,
    [int64] $EvidenceSizeBytes = 4GB,
    [string[]] $AdditionalInputPath = @(),
    [switch] $DryRun,
    [switch] $NoRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:InputLabel = 'S11BINPUTS'
$script:EvidenceLabel = 'S11BEVIDENCE'
$script:RequiredInputNames = @('runner.ps1', 'scenario.json', 'expected-runner.sha256', 'expected-artifacts.json')
$script:ReservedVolumeRootNames = @('SYSTEM VOLUME INFORMATION', '$RECYCLE.BIN')

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

function Assert-PlainFile {
    param([string] $Path, [string] $Label)
    $full = [IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { throw "$Label does not exist: $full" }
    $item = Get-Item -LiteralPath $full -ErrorAction Stop
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "$Label is a reparse point" }
    return $item
}

function Assert-PlainDirectory {
    param([string] $Path, [string] $Label)
    $full = [IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $full -PathType Container)) { throw "$Label does not exist: $full" }
    $item = Get-Item -LiteralPath $full -ErrorAction Stop
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

function Get-ValidatedInputContract {
    param([string] $Runner, [string] $Scenario, [string] $ExpectedArtifacts, [string[]] $OptionalPaths)
    $runnerItem = Assert-PlainFile $Runner 'runner.ps1'
    if ($runnerItem.Extension -ine '.ps1') { throw 'RunnerPath must be a PowerShell script' }
    $scenarioItem = Assert-PlainFile $Scenario 'scenario.json'
    $manifestItem = Assert-PlainFile $ExpectedArtifacts 'expected-artifacts.json'
    try {
        $scenarioObject = [IO.File]::ReadAllText($scenarioItem.FullName, [Text.Encoding]::UTF8) | ConvertFrom-Json -ErrorAction Stop
        if ($scenarioObject.schema -ne 'gentle-ai.yasb-limitora.reusable-vm-run/v1') { throw 'scenario.json schema mismatch' }
        if ([string]$scenarioObject.scenario -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$') { throw 'scenario.json scenario is unsafe or missing' }
        $manifestObject = [IO.File]::ReadAllText($manifestItem.FullName, [Text.Encoding]::UTF8) | ConvertFrom-Json -ErrorAction Stop
        if ($manifestObject.schema -ne 'gentle-ai.yasb-limitora.reusable-artifact-manifest/v1') { throw 'expected-artifacts.json schema mismatch' }
    } catch { throw "input contract validation failed: $($_.Exception.Message)" }
    $optional = @()
    foreach ($path in @($OptionalPaths)) {
        if ([string]::IsNullOrWhiteSpace($path)) { continue }
        $item = Get-Item -LiteralPath ([IO.Path]::GetFullPath($path)) -ErrorAction Stop
        if (Test-ReservedVolumeRootName $item.Name) { throw "optional input name is reserved at the volume root: $($item.Name)" }
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "optional input is a reparse point: $path" }
        $optional += $item.FullName
    }
    return [ordered]@{
        Runner = $runnerItem.FullName
        Scenario = $scenarioItem.FullName
        ExpectedArtifacts = $manifestItem.FullName
        RunnerSha256 = Get-HostSha256 $runnerItem.FullName
        Optional = $optional
    }
}

function New-RunVolumePlan {
    param(
        [System.Collections.IDictionary] $Contract,
        [string] $InputPath,
        [string] $EvidencePath,
        [int64] $InputBytes,
        [int64] $EvidenceBytes,
        [string[]] $OptionalPaths
    )
    if ($InputBytes -lt 64MB -or $EvidenceBytes -lt 64MB) { throw 'VHDX sizes must be at least 64 MiB' }
    $inputFull = [IO.Path]::GetFullPath($InputPath)
    $evidenceFull = [IO.Path]::GetFullPath($EvidencePath)
    if ([string]::Equals($inputFull, $evidenceFull, [StringComparison]::OrdinalIgnoreCase)) { throw 'input and evidence VHDX paths must be distinct' }
    if (Test-Path -LiteralPath $inputFull -PathType Leaf) { throw "input VHDX already exists: $inputFull" }
    if (Test-Path -LiteralPath $evidenceFull -PathType Leaf) { throw "evidence VHDX already exists: $evidenceFull" }
    return [ordered]@{
        inputVhdx = $inputFull
        evidenceVhdx = $evidenceFull
        inputLabel = $script:InputLabel
        evidenceLabel = $script:EvidenceLabel
        inputFiles = @($script:RequiredInputNames + @($OptionalPaths | ForEach-Object { [IO.Path]::GetFileName($_) }))
        runnerSha256 = $Contract.RunnerSha256
        dryRun = $true
    }
}

function Invoke-StorageCleanup {
    param([string] $Path)
    try {
        $image = Get-DiskImage -ImagePath $Path -ErrorAction SilentlyContinue
        if ($image -and $image.Attached) { Dismount-DiskImage -ImagePath $Path -ErrorAction SilentlyContinue | Out-Null }
    } catch { }
}

function Get-DiskForImage {
    param([string] $Path, [int] $TimeoutSeconds = 30)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $disk = Get-DiskImage -ImagePath $Path -ErrorAction Stop | Get-Disk -ErrorAction SilentlyContinue
        if ($disk) { return $disk }
        Start-Sleep -Seconds 1
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "VHDX did not surface as a disk within ${TimeoutSeconds}s: $Path"
}

function Mount-NewVolume {
    param([string] $Path, [string] $Label, [int64] $SizeBytes)
    New-VHD -Path $Path -Dynamic -SizeBytes $SizeBytes -ErrorAction Stop | Out-Null
    try {
        Mount-DiskImage -ImagePath $Path -ErrorAction Stop | Out-Null
        $disk = Get-DiskForImage $Path
        if ($disk.PartitionStyle -ne 'RAW') { throw "new VHDX is not RAW: $Path" }
        Initialize-Disk -Number $disk.Number -PartitionStyle GPT -Confirm:$false -ErrorAction Stop | Out-Null
        $partition = New-Partition -DiskNumber $disk.Number -UseMaximumSize -AssignDriveLetter -ErrorAction Stop
        if (-not $partition.DriveLetter) { throw "new VHDX has no drive letter: $Path" }
        Format-Volume -DriveLetter $partition.DriveLetter -FileSystem NTFS -NewFileSystemLabel $Label -Confirm:$false -ErrorAction Stop | Out-Null
        return ([string]$partition.DriveLetter + ':\')
    } catch {
        Invoke-StorageCleanup $Path
        throw
    }
}

function Copy-DeclaredInput {
    param([string] $Source, [string] $DestinationRoot)
    $sourceItem = Get-Item -LiteralPath $Source -ErrorAction Stop
    $destination = Join-Path $DestinationRoot $sourceItem.Name
    if ($sourceItem -is [IO.FileInfo]) {
        if (Test-Path -LiteralPath $destination) { throw "duplicate input file: $($sourceItem.Name)" }
        Copy-Item -LiteralPath $sourceItem.FullName -Destination $destination -ErrorAction Stop
    } else {
        if (Test-Path -LiteralPath $destination) { throw "duplicate input directory: $($sourceItem.Name)" }
        Copy-Item -LiteralPath $sourceItem.FullName -Destination $destination -Recurse -ErrorAction Stop
    }
}

function New-RunVolumes {
    param(
        [string] $Runner,
        [string] $Scenario,
        [string] $ExpectedArtifacts,
        [string] $InputPath,
        [string] $EvidencePath,
        [int64] $InputBytes = 1GB,
        [int64] $EvidenceBytes = 4GB,
        [string[]] $OptionalPaths = @(),
        [switch] $DryRun
    )
    $contract = Get-ValidatedInputContract $Runner $Scenario $ExpectedArtifacts $OptionalPaths
    $plan = New-RunVolumePlan $contract $InputPath $EvidencePath $InputBytes $EvidenceBytes $OptionalPaths
    if ($DryRun) { return $plan }
    $inputRoot = $null
    $evidenceRoot = $null
    try {
        $inputRoot = Mount-NewVolume $plan.inputVhdx $plan.inputLabel $InputBytes
        [IO.File]::Copy($contract.Runner, (Join-Path $inputRoot 'runner.ps1'))
        [IO.File]::Copy($contract.Scenario, (Join-Path $inputRoot 'scenario.json'))
        [IO.File]::WriteAllText((Join-Path $inputRoot 'expected-runner.sha256'), $contract.RunnerSha256 + "`n", [Text.UTF8Encoding]::new($false))
        [IO.File]::Copy($contract.ExpectedArtifacts, (Join-Path $inputRoot 'expected-artifacts.json'))
        foreach ($optional in @($contract.Optional)) { Copy-DeclaredInput $optional $inputRoot }
        $inputDigest = Get-InputTreeDigest $inputRoot
        Dismount-DiskImage -ImagePath $plan.inputVhdx -ErrorAction Stop | Out-Null
        $inputRoot = $null
        $evidenceRoot = Mount-NewVolume $plan.evidenceVhdx $plan.evidenceLabel $EvidenceBytes
        Dismount-DiskImage -ImagePath $plan.evidenceVhdx -ErrorAction Stop | Out-Null
        $evidenceRoot = $null
        $plan.inputTreeSha256 = $inputDigest
        $plan.dryRun = $false
        return $plan
    } catch {
        if ($inputRoot) { Invoke-StorageCleanup $plan.inputVhdx }
        if ($evidenceRoot) { Invoke-StorageCleanup $plan.evidenceVhdx }
        throw
    }
}

if (-not $NoRun) {
    $result = New-RunVolumes -Runner $RunnerPath -Scenario $ScenarioPath -ExpectedArtifacts $ExpectedArtifactsPath `
        -InputPath $InputVhdxPath -EvidencePath $EvidenceVhdxPath -InputBytes $InputSizeBytes `
        -EvidenceBytes $EvidenceSizeBytes -OptionalPaths $AdditionalInputPath -DryRun:$DryRun
    $result | ConvertTo-Json -Depth 8
}
