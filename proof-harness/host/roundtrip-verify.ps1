<#[CmdletBinding()]
.SYNOPSIS
    Verify an authored data ISO against its staging tree and prove it is dismounted.
.DESCRIPTION
    Mounts the ISO read-only, compares the complete member set and SHA-256 bytes with
    staging, then dismounts it. The final negative mounted-state assertion targets the
    exact image path; it does not treat an unrelated mounted image as this ISO.
    No setup, uninstaller, VM, checkpoint, or product process is executed.
#>
[CmdletBinding()]
param(
    [string] $IsoPath = '',
    [string] $StagingRoot = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = [IO.Path]::GetFullPath($PSScriptRoot)
if ([string]::IsNullOrWhiteSpace($IsoPath)) { $IsoPath = Join-Path $scriptRoot 'inputs.iso' }
if ([string]::IsNullOrWhiteSpace($StagingRoot)) { $StagingRoot = Join-Path $scriptRoot 'iso-staging' }
$isoPath = [IO.Path]::GetFullPath($IsoPath)
$stagingRoot = [IO.Path]::GetFullPath($StagingRoot)

function Get-HostSha256([string] $Path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $stream = [IO.File]::OpenRead($Path)
        try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
        finally { $stream.Dispose() }
    } finally { $sha.Dispose() }
}

function Get-RelativePath([string] $Root, [string] $Full) {
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $fullPath = [IO.Path]::GetFullPath($Full)
    $prefix = $rootFull + '\'
    if (-not $fullPath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "path '$Full' is outside root '$Root'"
    }
    return $fullPath.Substring($prefix.Length).Replace('\', '/')
}

function Assert-File([string] $Path, [string] $Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label missing: $Path" }
}

function Assert-IsoDismounted([string] $isoPath) {
    # Query only this image. Get-DiskImage without -ImagePath can report an unrelated
    # mounted image and would make the verifier's negative assertion unsound. Query errors,
    # a missing image, and an ambiguous response all fail closed rather than becoming PASS.
    try {
        $images = @(Get-DiskImage -ImagePath $isoPath -ErrorAction Stop)
    } catch {
        throw "unable to query ISO mount state for '$isoPath': $($_.Exception.Message)"
    }
    if ($images.Count -ne 1) {
        throw "unable to query ISO mount state for '$isoPath': expected one image, found $($images.Count)"
    }
    $attachedProperty = $images[0].PSObject.Properties['Attached']
    if ($null -eq $attachedProperty -or $attachedProperty.Value -isnot [bool]) {
        throw "unable to query ISO mount state for '$isoPath': Attached state is unavailable"
    }
    if ($attachedProperty.Value) { throw "ISO still mounted after dismount attempt: $isoPath" }
}

Assert-File $isoPath 'ISO'
if (-not (Test-Path -LiteralPath $stagingRoot -PathType Container)) { throw "staging root missing: $stagingRoot" }

$stagedFiles = @(Get-ChildItem -LiteralPath $stagingRoot -Recurse -File)
$declared = [Collections.Generic.SortedSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($file in $stagedFiles) { $declared.Add((Get-RelativePath $stagingRoot $file.FullName)) | Out-Null }

$mounted = $false
$tempRoot = $null
$failures = [Collections.Generic.List[string]]::new()
try {
    $mount = Mount-DiskImage -ImagePath $isoPath -Access ReadOnly -PassThru -ErrorAction Stop
    $mounted = $true
    $volume = @($mount | Get-Volume -ErrorAction Stop | Where-Object { $_.DriveLetter } | Select-Object -First 1)
    if ($volume.Count -ne 1) { throw 'mounted ISO has no drive letter' }
    $isoRoot = "$($volume[0].DriveLetter):\"
    $isoFiles = @(Get-ChildItem -LiteralPath $isoRoot -Recurse -File)
    $members = [Collections.Generic.SortedSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($file in $isoFiles) { $members.Add((Get-RelativePath $isoRoot $file.FullName)) | Out-Null }

    foreach ($member in $declared) {
        if (-not $members.Contains($member)) { $failures.Add("missing ISO member: $member") | Out-Null }
    }
    foreach ($member in $members) {
        if (-not $declared.Contains($member)) { $failures.Add("unexpected ISO member: $member") | Out-Null }
    }

    $tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('roundtrip-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
    foreach ($file in $isoFiles) {
        $relative = Get-RelativePath $isoRoot $file.FullName
        $destination = Join-Path $tempRoot ($relative -replace '/', '\')
        $parent = Split-Path -Parent $destination
        if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
    }
    foreach ($file in $stagedFiles) {
        $relative = Get-RelativePath $stagingRoot $file.FullName
        $roundtrip = Join-Path $tempRoot ($relative -replace '/', '\')
        if (-not (Test-Path -LiteralPath $roundtrip -PathType Leaf)) { continue }
        if ((Get-HostSha256 $file.FullName) -ne (Get-HostSha256 $roundtrip)) {
            $failures.Add("member hash mismatch: $relative") | Out-Null
        }
    }
} finally {
    if ($null -ne $tempRoot -and (Test-Path -LiteralPath $tempRoot)) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
    if ($mounted) {
        Dismount-DiskImage -ImagePath $isoPath -ErrorAction SilentlyContinue | Out-Null
        Start-Sleep -Seconds 1
        try { Assert-IsoDismounted $isoPath } catch { $failures.Add($_.Exception.Message) | Out-Null }
    }
}

Write-Output "ISO members staged=$($declared.Count)"
if ($failures.Count -gt 0) {
    foreach ($failure in $failures) { Write-Output "FAIL $failure" }
    Write-Output "VERDICT: FAIL ($($failures.Count) violation(s))"
    exit 1
}
Write-Output 'PASS ISO member set, hashes, and dismount assertion'
exit 0
