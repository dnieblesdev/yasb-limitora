[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $EvidenceRoot,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')]
    [string] $Scenario,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')]
    [string] $Phase,
    [string[]] $LogPath = @(),
    [string[]] $HolderRecordPath = @()
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
    if (-not $candidateFull.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) { throw "$Label is outside the declared root" }
    return $candidateFull
}

function Assert-EvidenceRoot([string] $Path) {
    $item = Assert-ExistingPathChain $Path 'evidence root'
    if (-not $item.PSIsContainer) { throw 'evidence root must be a directory' }
    $drive = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($item.FullName))
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

function Get-RelativeGuestPath([string] $Root, [string] $Path) {
    $rootFull = [IO.Path]::GetFullPath($Root)
    $candidateFull = [IO.Path]::GetFullPath($Path)
    while ($rootFull.EndsWith('\') -or $rootFull.EndsWith('/')) {
        $rootFull = $rootFull.Substring(0, $rootFull.Length - 1)
    }
    if ([string]::Equals($candidateFull, $rootFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'candidate path equals relative-path root'
    }
    $rootPrefix = $rootFull + [IO.Path]::DirectorySeparatorChar
    if (-not $candidateFull.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'candidate path is outside relative-path root'
    }
    return $candidateFull.Substring($rootPrefix.Length).Replace([IO.Path]::DirectorySeparatorChar, '/').Replace([IO.Path]::AltDirectorySeparatorChar, '/')
}

function Get-TreeDigest([string] $Root) {
    $resolved = [IO.Path]::GetFullPath($Root)
    if (-not (Test-Path -LiteralPath $resolved -PathType Container)) { return [ordered]@{ present = $false; root = $resolved; files = @() } }
    Assert-ExistingPathChain $resolved 'tree root' | Out-Null
    $pending = [Collections.Generic.Stack[IO.DirectoryInfo]]::new()
    $pending.Push([IO.DirectoryInfo]::new($resolved))
    $files = [Collections.Generic.List[object]]::new()
    [int64]$totalBytes = 0
    while ($pending.Count -gt 0) {
        $directory = $pending.Pop()
        foreach ($entry in $directory.EnumerateFileSystemInfos('*', [IO.SearchOption]::TopDirectoryOnly)) {
            if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { continue }
            if ($entry -is [IO.DirectoryInfo]) { $pending.Push([IO.DirectoryInfo]$entry); continue }
            if ($files.Count -ge 10000) { throw "tree file-count bound exceeded for $resolved" }
            if ($totalBytes + [int64]$entry.Length -gt 536870912) { throw "tree byte bound exceeded for $resolved" }
            $hash = (Get-FileHash -LiteralPath $entry.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            $files.Add([ordered]@{ path = Get-RelativeGuestPath $resolved $entry.FullName; size = [int64]$entry.Length; sha256 = $hash })
            $totalBytes += [int64]$entry.Length
        }
    }
    return [ordered]@{ present = $true; root = $resolved; files = @($files | Sort-Object path) }
}

function Get-StringDigest([string] $Value) {
    if ($null -eq $Value) { return $null }
    $bytes = [Text.Encoding]::Unicode.GetBytes($Value)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [ordered]@{ length = $Value.Length; sha256 = ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant() } }
    finally { $sha.Dispose() }
}

function Get-RegistrySnapshot([string] $Subkey) {
    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser, [Microsoft.Win32.RegistryView]::Default)
    try {
        $key = $base.OpenSubKey($Subkey, $false)
        if ($null -eq $key) { return [ordered]@{ path = "HKCU:\$Subkey"; present = $false; values = @() } }
        try {
            $names = @($key.GetValueNames() | Sort-Object)
            if ($names.Count -gt 128) { throw 'registry value-count bound exceeded' }
            $values = foreach ($name in $names) {
                $value = $key.GetValue($name, $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
                $kind = $key.GetValueKind($name).ToString()
                $entry = [ordered]@{ name = $name; kind = $kind }
                if ($kind -in @('String', 'ExpandString')) { $entry.value = [string]$value }
                elseif ($kind -eq 'DWord') { $entry.value = [int64]$value }
                else { $entry.valueDigest = Get-StringDigest ([string]$value) }
                [pscustomobject]$entry
            }
            return [ordered]@{ path = "HKCU:\$Subkey"; present = $true; values = @($values) }
        } finally { $key.Dispose() }
    } finally { $base.Dispose() }
}

$evidence = Assert-EvidenceRoot $EvidenceRoot
$scenarioRoot = Join-Path $evidence $Scenario
$phaseRoot = Join-Path $scenarioRoot $Phase
if (Test-Path -LiteralPath $scenarioRoot) {
    $scenarioItem = Assert-ExistingPathChain $scenarioRoot 'scenario directory'
    if (-not $scenarioItem.PSIsContainer) { throw 'scenario path must be a directory' }
} else {
    New-Item -ItemType Directory -Path $scenarioRoot | Out-Null
    Assert-ExistingPathChain $scenarioRoot 'scenario directory' | Out-Null
}
if (Test-Path -LiteralPath $phaseRoot) { throw 'phase already exists; evidence collision refused' }
New-Item -ItemType Directory -Path $phaseRoot | Out-Null
Assert-ExistingPathChain $phaseRoot 'phase directory' | Out-Null

$localAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
$appRoot = Join-Path $localAppData 'Programs\yasb-limitora'
$stateRoot = Join-Path $localAppData 'yasb-limitora'
$uninstallSubkey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{55D372A6-1DA5-41BE-B7AB-65CAB362E620}_is1'
$pathBase = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser, [Microsoft.Win32.RegistryView]::Default)
try {
    $environmentKey = $pathBase.OpenSubKey('Environment', $false)
    try {
        if ($null -eq $environmentKey -or $null -eq $environmentKey.GetValue('Path', $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)) {
            $pathRecord = [ordered]@{ present = $false; kind = $null; valueDigest = $null }
        } else {
            $rawPath = [string]$environmentKey.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
            $pathRecord = [ordered]@{ present = $true; kind = $environmentKey.GetValueKind('Path').ToString(); valueDigest = Get-StringDigest $rawPath }
        }
    } finally { if ($null -ne $environmentKey) { $environmentKey.Dispose() } }
} finally { $pathBase.Dispose() }

$logRecords = foreach ($path in $LogPath) {
    $log = Assert-Descendant $evidence $path 'owned log'
    $item = Assert-ExistingPathChain $log 'owned log' $true
    [ordered]@{ path = $log; size = [int64]$item.Length; sha256 = (Get-FileHash -LiteralPath $log -Algorithm SHA256).Hash.ToLowerInvariant() }
}
$holderRecords = foreach ($path in $HolderRecordPath) {
    $artifact = Assert-Descendant $evidence $path 'holder record'
    $item = Assert-ExistingPathChain $artifact 'holder record' $true
    [ordered]@{ path = $artifact; size = [int64]$item.Length; sha256 = (Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash.ToLowerInvariant() }
}
$processes = @(Get-CimInstance -ClassName Win32_Process -Filter "Name = 'yasb-limitora.exe' OR Name = 'yasb.exe'" | Select-Object @{Name = 'name'; Expression = { $_.Name }}, @{Name = 'processId'; Expression = { [int]$_.ProcessId }}, @{Name = 'executablePath'; Expression = { $_.ExecutablePath }})
$record = [ordered]@{
    schema = 'gentle-ai.yasb-limitora.s11b-guest-state/v3'
    capturedUtc = [DateTime]::UtcNow.ToString('o')
    scenario = $Scenario
    phase = $Phase
    exactRoots = [ordered]@{ app = $appRoot; state = $stateRoot }
    uninstallKey = Get-RegistrySnapshot $uninstallSubkey
    userPath = $pathRecord
    relevantProcesses = $processes
    setupUninstallLogs = @($logRecords)
    holderRecords = @($holderRecords)
    trees = [ordered]@{ app = Get-TreeDigest $appRoot; state = Get-TreeDigest $stateRoot }
}
$out = Join-Path $phaseRoot 'state-capture.json'
if (Test-Path -LiteralPath $out) { throw 'state-capture.json already exists; overwrite refused' }
Write-ExclusiveText $out (($record | ConvertTo-Json -Depth 12) + "`n")
Write-Output "capture-state: wrote $out"
