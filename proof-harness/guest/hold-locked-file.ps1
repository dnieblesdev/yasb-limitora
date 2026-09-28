[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $GuestFile,
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $GuestRoot,
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $ReleaseSignal,
    [string] $EvidenceRoot,
    [string] $Scenario,
    [string] $Phase
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

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
    if (-not $candidateFull.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) { throw "$Label is outside the explicit guest root" }
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

function Get-Sha256([string] $Path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $fs = [IO.File]::OpenRead($Path)
        try { return ([BitConverter]::ToString($sha.ComputeHash($fs))).Replace('-', '').ToLowerInvariant() }
        finally { $fs.Dispose() }
    }
    finally { $sha.Dispose() }
}

$root = Assert-ExistingPathChain $GuestRoot 'guest root'
if (-not $root.PSIsContainer) { throw 'guest root must be a directory' }
$filePath = Assert-Descendant $root.FullName $GuestFile 'locked guest file'
$file = Assert-ExistingPathChain $filePath 'locked guest file' $true
$signalPath = Assert-Descendant $root.FullName $ReleaseSignal 'release signal'
$signalParent = [IO.Path]::GetDirectoryName($signalPath)
Assert-ExistingPathChain $signalParent 'release-signal parent' | Out-Null
if (Test-Path -LiteralPath $signalPath) {
    Assert-ExistingPathChain $signalPath 'release signal' $true | Out-Null
    throw 'release signal already exists; a fresh explicit signal is required'
}

$wantsEvidence = (-not [string]::IsNullOrWhiteSpace($EvidenceRoot)) -or (-not [string]::IsNullOrWhiteSpace($Scenario)) -or (-not [string]::IsNullOrWhiteSpace($Phase))
$recordRoot = $null
if ($wantsEvidence) {
    if ([string]::IsNullOrWhiteSpace($EvidenceRoot) -or [string]::IsNullOrWhiteSpace($Scenario) -or [string]::IsNullOrWhiteSpace($Phase)) {
        throw 'holder evidence requires EvidenceRoot, Scenario, and Phase together'
    }
    if ($Scenario -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$') { throw 'scenario identifier is unsafe' }
    if ($Phase -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$') { throw 'phase identifier is unsafe' }
    $evidence = Assert-EvidenceRoot $EvidenceRoot
    $scenarioRoot = Join-Path $evidence $Scenario
    if (Test-Path -LiteralPath $scenarioRoot) {
        $scenarioItem = Assert-ExistingPathChain $scenarioRoot 'scenario directory'
        if (-not $scenarioItem.PSIsContainer) { throw 'scenario path must be a directory' }
    } else {
        New-Item -ItemType Directory -Path $scenarioRoot | Out-Null
        Assert-ExistingPathChain $scenarioRoot 'scenario directory' | Out-Null
    }
    $phaseRoot = Join-Path $scenarioRoot $Phase
    if (Test-Path -LiteralPath $phaseRoot) { throw 'phase already exists; evidence collision refused' }
    New-Item -ItemType Directory -Path $phaseRoot | Out-Null
    Assert-ExistingPathChain $phaseRoot 'phase directory' | Out-Null
    $recordRoot = $phaseRoot
}

$holderProcessId = $PID
$startedUtc = [DateTime]::UtcNow
$stream = $null
try {
    $stream = [IO.File]::Open($file.FullName, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    if ($null -ne $recordRoot) {
        $start = [ordered]@{
            schema = 'gentle-ai.yasb-limitora.s11b-holder/v1'
            phase = 'start'
            guestFile = $file.FullName
            guestFileSize = [int64]$file.Length
            guestFileSha256 = Get-Sha256 $file.FullName
            guestRoot = $root.FullName
            releaseSignal = $signalPath
            releaseSignalPresentAtStart = $false
            sharingMode = 'FileAccess.Read with FileShare.ReadWrite; delete sharing is denied for the whole hold'
            holderProcessId = $holderProcessId
            startedUtc = $startedUtc.ToString('o')
        }
        Write-ExclusiveText (Join-Path $recordRoot 'holder-start.json') (($start | ConvertTo-Json -Depth 6) + "`n")
    }
    Write-Output "hold-locked-file: holding $($file.FullName); waiting for explicit guest-local release signal"
    while ($true) {
        if (Test-Path -LiteralPath $signalPath) {
            Assert-ExistingPathChain $signalPath 'release signal' $true | Out-Null
            break
        }
        Start-Sleep -Milliseconds 250
    }
    $releasedUtc = [DateTime]::UtcNow
    if ($null -ne $recordRoot) {
        $signalItem = Assert-ExistingPathChain $signalPath 'release signal' $true
        $end = [ordered]@{
            schema = 'gentle-ai.yasb-limitora.s11b-holder/v1'
            phase = 'end'
            guestFile = $file.FullName
            guestRoot = $root.FullName
            releaseSignal = $signalPath
            releaseSignalSize = [int64]$signalItem.Length
            releaseSignalSha256 = Get-Sha256 $signalItem.FullName
            releaseReason = 'explicit guest-local release signal observed'
            exitPath = 'normal-exit-after-explicit-signal'
            holderProcessId = $holderProcessId
            startedUtc = $startedUtc.ToString('o')
            releasedUtc = $releasedUtc.ToString('o')
            heldSeconds = [math]::Round(($releasedUtc - $startedUtc).TotalSeconds, 3)
        }
        Write-ExclusiveText (Join-Path $recordRoot 'holder-end.json') (($end | ConvertTo-Json -Depth 6) + "`n")
    }
    Write-Output 'hold-locked-file: explicit release signal observed; closing normally'
    exit 0
} catch {
    Write-Error "hold-locked-file: $($_.Exception.Message)"
    exit 2
} finally {
    if ($null -ne $stream) { $stream.Dispose() }
}