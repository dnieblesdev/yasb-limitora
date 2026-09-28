[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('setup', 'uninstall')]
    [string] $Kind,
    [string] $ReadOnlyMediaRoot,
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $ExecutablePath,
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $EvidenceRoot,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')]
    [string] $Scenario,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')]
    [string] $Phase,
    [string[]] $ArgumentList = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$UninstallSubkey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{55D372A6-1DA5-41BE-B7AB-65CAB362E620}_is1'

function Assert-ExistingPathChain([string] $Path, [string] $Label, [bool] $RequireFile = $false) {
    $full = [IO.Path]::GetFullPath($Path)
    if (-not [IO.Path]::IsPathRooted($full) -or $full.StartsWith('\\')) {
        throw "$Label must be a local rooted path"
    }
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
        if (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "$Label has a reparse-point ancestor: $($cursor.FullName)"
        }
        $parent = $cursor.Parent
        if ($null -eq $parent -or $parent.FullName -eq $cursor.FullName) { break }
        $cursor = $parent
    }
    return $item
}

function Assert-Descendant([string] $Root, [string] $Candidate, [string] $Label) {
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    $candidateFull = [IO.Path]::GetFullPath($Candidate)
    if (-not $candidateFull.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label is outside the declared root"
    }
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

function Assert-ReadOnlyMedia([string] $Path) {
    $item = Assert-ExistingPathChain $Path 'read-only media root'
    if (-not $item.PSIsContainer) { throw 'read-only media root must be a directory' }
    $drive = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($item.FullName))
    if (-not $drive.IsReady -or $drive.DriveType -ne [IO.DriveType]::CDRom) {
        throw 'read-only media root must be a mounted CD-ROM/data ISO volume'
    }
    return $item.FullName
}

function Get-RecordedUninstaller {
    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
        [Microsoft.Win32.RegistryHive]::CurrentUser,
        [Microsoft.Win32.RegistryView]::Default)
    try {
        $key = $base.OpenSubKey($UninstallSubkey, $false)
        if ($null -eq $key) { throw 'exact production uninstall key is absent' }
        try {
            $value = $key.GetValue('UninstallString', $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
            if ($value -isnot [string]) { throw 'exact production UninstallString is not a string' }
            $match = [regex]::Match($value, '^\s*"([^"]+)"\s*$')
            if (-not $match.Success) { throw 'exact production UninstallString is not one quoted executable path' }
            return $match.Groups[1].Value
        } finally { $key.Dispose() }
    } finally { $base.Dispose() }
}

function Assert-SafeArgument([string] $Value) {
    if ($null -eq $Value -or $Value.IndexOf([char]0) -ge 0 -or $Value.Length -gt 4096) {
        throw 'argument is empty, oversized, or contains a control character'
    }
    if ($Value -match '(?i)(token|password|secret|credential|cookie|api.?key|authorization)') {
        throw 'argument rejected because it may contain a secret'
    }
    if ($Value -match '(?i)^[/\\-]?log(?:=|\s|$)') {
        throw 'caller-supplied log path is forbidden; runner owns the exact log path'
    }
}

function Write-ExclusiveText([string] $Path, [string] $Text) {
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $writer = [IO.StreamWriter]::new($stream, [Text.UTF8Encoding]::new($false))
        try { $writer.Write($Text) } finally { $writer.Dispose() }
    } finally { $stream.Dispose() }
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
$runRoot = Join-Path $phaseRoot ('run-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $runRoot | Out-Null
Assert-ExistingPathChain $runRoot 'run directory' | Out-Null

$exe = [IO.Path]::GetFullPath($ExecutablePath)
if ($Kind -eq 'setup') {
    if ([string]::IsNullOrWhiteSpace($ReadOnlyMediaRoot)) { throw 'setup requires read-only media root' }
    $media = Assert-ReadOnlyMedia $ReadOnlyMediaRoot
    $exe = Assert-Descendant $media $exe 'setup executable'
    $exeItem = Assert-ExistingPathChain $exe 'setup executable' $true
} else {
    $recorded = [IO.Path]::GetFullPath((Get-RecordedUninstaller))
    if (-not [string]::Equals($exe, $recorded, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'supplied uninstall executable does not exactly match quoted production UninstallString'
    }
    $localAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
    $appRoot = Join-Path $localAppData 'Programs\yasb-limitora'
    Assert-Descendant $appRoot $exe 'uninstall executable' | Out-Null
    $exeItem = Assert-ExistingPathChain $exe 'uninstall executable' $true
}
if ($exeItem.Extension -ine '.exe') { throw 'executable must be an .exe file' }
if ($ArgumentList.Count -gt 32) { throw 'argument count bound exceeded' }
foreach ($argument in $ArgumentList) { Assert-SafeArgument $argument }

$stdoutPath = Join-Path $runRoot 'stdout.txt'
$stderrPath = Join-Path $runRoot 'stderr.txt'
$logPath = Join-Path $runRoot "$Kind.log"
$recordPath = Join-Path $runRoot 'run-record.json'
$argv = @($exe) + @($ArgumentList) + @("/LOG=$logPath")
if ($argv.Count -gt 34) { throw 'recorded argv bound exceeded' }
$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
$start = [DateTime]::UtcNow
$process = Start-Process -FilePath $exe -ArgumentList (@($ArgumentList) + "/LOG=$logPath") -WorkingDirectory $exeItem.DirectoryName -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru -Wait
$finish = [DateTime]::UtcNow

$output = @(
    [ordered]@{ path = $stdoutPath; size = [int64](Get-Item -LiteralPath $stdoutPath).Length; sha256 = (Get-FileHash -LiteralPath $stdoutPath -Algorithm SHA256).Hash.ToLowerInvariant() }
    [ordered]@{ path = $stderrPath; size = [int64](Get-Item -LiteralPath $stderrPath).Length; sha256 = (Get-FileHash -LiteralPath $stderrPath -Algorithm SHA256).Hash.ToLowerInvariant() }
)
if (Test-Path -LiteralPath $logPath) {
    Assert-ExistingPathChain $logPath 'owned setup/uninstall log' $true | Out-Null
    $log = [ordered]@{ present = $true; path = $logPath; size = [int64](Get-Item -LiteralPath $logPath).Length; sha256 = (Get-FileHash -LiteralPath $logPath -Algorithm SHA256).Hash.ToLowerInvariant() }
} else {
    $log = [ordered]@{ present = $false; path = $logPath; size = $null; sha256 = $null }
}
$record = [ordered]@{
    schema = 'gentle-ai.yasb-limitora.s11b-guest-run/v2'
    kind = $Kind
    scenario = $Scenario
    phase = $Phase
    executable = [ordered]@{ path = $exe; size = [int64]$exeItem.Length; sha256 = $hash }
    argv = $argv
    startedUtc = $start.ToString('o')
    finishedUtc = $finish.ToString('o')
    exitCode = [int]$process.ExitCode
    output = $output
    exactLog = $log
}
Write-ExclusiveText $recordPath (($record | ConvertTo-Json -Depth 12) + "`n")
Write-Output "run-setup-uninstall: wrote $recordPath"
exit $process.ExitCode
