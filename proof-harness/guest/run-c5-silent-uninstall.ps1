[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $EvidenceRoot,
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $ScenarioPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScenarioName = 'silent-uninstall-with-state-root'
$SetupName = 'yasb-limitora-0.2.0-setup.exe'
$SetupSize = [int64]11054574
$SetupHash = '1d58f3618f5b22ddccacc7be2dcf8e3a1e9a90dba57dffe431d8ca8ae6df3394'
$LegacyScenarioHash = '8aca8127167fc5ec0ec143c563e1b14c1d77bf763c8203d2095bd1c515a37c93'
$FixtureHash = 'e16c422f5a2593dd4bfcc1cf5979cfad382769422953ff10202986be8f0a1795'
$CaptureHash = '3b005ddbcbce16b70532b85237ca426ba560fb901e4c55602d804b015f1d49f7'
$SilentArguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART')
$UninstallSubkey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{55D372A6-1DA5-41BE-B7AB-65CAB362E620}_is1'

function Get-Property($Object, [string] $Name) {
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Assert-LocalPath([string] $Path, [string] $Label, [bool] $File = $false) {
    $full = [IO.Path]::GetFullPath($Path)
    if (-not [IO.Path]::IsPathRooted($full) -or $full.StartsWith('\\')) { throw "$Label must be a local rooted path" }
    if (-not (Test-Path -LiteralPath $full)) { throw "$Label does not exist" }
    $item = Get-Item -LiteralPath $full -ErrorAction Stop
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "$Label is a reparse point" }
    if ($File -and $item -isnot [IO.FileInfo]) { throw "$Label must be a regular file" }
    return $item
}

function Assert-Child([string] $Root, [string] $Relative, [string] $Label) {
    if ([string]::IsNullOrWhiteSpace($Relative) -or [IO.Path]::IsPathRooted($Relative) -or $Relative.Contains('..')) { throw "$Label must be a relative child path" }
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $candidate = [IO.Path]::GetFullPath((Join-Path $Root $Relative))
    if (-not $candidate.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) { throw "$Label escapes its root" }
    return $candidate
}

function Get-Hash([string] $Path) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }

function Write-ExclusiveJson([string] $Path, $Value) {
    if (Test-Path -LiteralPath $Path) { throw "refusing to overwrite $Path" }
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes((ConvertTo-Json $Value -Depth 12) + "`n")
    [IO.File]::WriteAllBytes($Path, $bytes)
}

function Read-Json([string] $Path, [string] $Label) {
    Assert-LocalPath $Path $Label $true | Out-Null
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Assert-ExitCode($Code, [string] $Label) {
    if ($Code -is [bool] -or $Code -isnot [int] -and $Code -isnot [long]) { throw "$Label returned a malformed exit code" }
    if ([int64]$Code -ne 0) { throw "$Label returned unexpected exit code $Code" }
}

function Invoke-C5Process([string] $Kind, [string] $Phase, [string] $Executable, [string[]] $Arguments, [string] $WorkingDirectory, [string] $Evidence) {
    $phaseRoot = Join-Path (Join-Path $Evidence $ScenarioName) $Phase
    New-Item -ItemType Directory -Path $phaseRoot -Force | Out-Null
    $stdout = Join-Path $phaseRoot 'stdout.txt'
    $stderr = Join-Path $phaseRoot 'stderr.txt'
    $executableItem = Get-Item -LiteralPath $Executable -ErrorAction Stop
    if ($executableItem -isnot [IO.FileInfo]) { throw "executable is not a regular file: $Executable" }
    $executableIdentity = [ordered]@{
        path = $executableItem.FullName
        present = $true
        name = $executableItem.Name
        size = [int64]$executableItem.Length
        sha256 = Get-Hash $executableItem.FullName
    }
    $started = [DateTime]::UtcNow
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -Wait
    $finished = [DateTime]::UtcNow
    $code = [int]$process.ExitCode
    $record = [ordered]@{
        schema = 'gentle-ai.yasb-limitora.c5-run/v1'
        kind = $Kind
        phase = $Phase
        executable = $executableIdentity
        arguments = @($Arguments)
        startedUtc = $started.ToString('o')
        finishedUtc = $finished.ToString('o')
        exitCode = $code
        stdout = [ordered]@{ path = $stdout; size = [int64](Get-Item -LiteralPath $stdout).Length; sha256 = Get-Hash $stdout }
        stderr = [ordered]@{ path = $stderr; size = [int64](Get-Item -LiteralPath $stderr).Length; sha256 = Get-Hash $stderr }
        dialogAnswerAttempted = $false
    }
    Write-ExclusiveJson (Join-Path $phaseRoot 'run-record.json') $record
    Assert-ExitCode $code "$Kind/$Phase"
    return $record
}

function Invoke-Capture([string] $CapturePath, [string] $Phase, [string] $Evidence) {
    & $CapturePath -EvidenceRoot $Evidence -Scenario $ScenarioName -Phase $Phase 2>&1 | Out-Null
    $capturePath = Join-Path (Join-Path (Join-Path $Evidence $ScenarioName) $Phase) 'state-capture.json'
    if (-not (Test-Path -LiteralPath $capturePath)) { throw "capture/$Phase produced no state-capture.json" }
    return (Read-Json $capturePath "capture/$Phase")
}

function Get-RegistryUninstaller {
    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser, [Microsoft.Win32.RegistryView]::Default)
    try {
        $key = $base.OpenSubKey($UninstallSubkey, $false)
        if ($null -eq $key) { throw 'installed uninstall key is missing' }
        try {
            $value = $key.GetValue('UninstallString', $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
            if ($value -isnot [string]) { throw 'installed UninstallString is not a string' }
            $match = [regex]::Match($value, '^\s*"([^"]+)"\s*$')
            if (-not $match.Success) { throw 'installed UninstallString is not one quoted executable path' }
            return $match.Groups[1].Value
        } finally { $key.Dispose() }
    } finally { $base.Dispose() }
}

$scenarioFull = [IO.Path]::GetFullPath($ScenarioPath)
$inputRoot = Split-Path -Parent $scenarioFull
Assert-LocalPath $inputRoot 'input root' | Out-Null
$scenario = Read-Json $scenarioFull 'scenario.json'
if ((Get-Property $scenario 'schema') -ne 'gentle-ai.yasb-limitora.reusable-vm-run/v1' -or (Get-Property $scenario 'scenario') -ne $ScenarioName) { throw 'generic scenario identity mismatch' }
$rootDialogProperty = $scenario.PSObject.Properties['dialogAnswers']
if ($null -eq $rootDialogProperty -or @($rootDialogProperty.Value).Count -ne 0) { throw 'generic scenario must declare no dialog answers' }
$stepsPath = Assert-Child $inputRoot 'c5-steps.json' 'C5 step manifest'
$steps = Read-Json $stepsPath 'c5-steps.json'
if ((Get-Property $steps 'schema') -ne 'gentle-ai.yasb-limitora.c5-silent-uninstall/v1' -or (Get-Property $steps 'scenario') -ne $ScenarioName) { throw 'C5 step manifest identity mismatch' }
$stepDialogProperty = $steps.PSObject.Properties['dialogAnswers']
if ($null -eq $stepDialogProperty -or @($stepDialogProperty.Value).Count -ne 0) { throw 'C5 steps must declare no dialog answers' }
if ((Get-Property $steps 'legacyScenarioSha256') -ne $LegacyScenarioHash) { throw 'legacy scenario hash mismatch' }
$setup = Get-Property $steps 'setup'
if ((Get-Property $setup 'name') -ne $SetupName -or [int64](Get-Property $setup 'size') -ne $SetupSize -or (Get-Property $setup 'sha256') -ne $SetupHash) { throw 'setup declaration mismatch' }
$arguments = @((Get-Property $steps 'silentArguments'))
if (($arguments -join "`n") -ne ($SilentArguments -join "`n")) { throw 'silent argument declaration mismatch' }

$setupPath = Assert-Child $inputRoot $SetupName 'setup executable'
$setupItem = Assert-LocalPath $setupPath 'setup executable' $true
if ($setupItem.Length -ne $SetupSize -or (Get-Hash $setupPath) -ne $SetupHash) { throw 'setup executable size or SHA-256 mismatch' }
$capturePath = Assert-Child $inputRoot 'capture-state.ps1' 'capture-state script'
Assert-LocalPath $capturePath 'capture-state script' $true | Out-Null
if ((Get-Hash $capturePath) -ne $CaptureHash) { throw 'staged capture-state.ps1 hash mismatch' }
$fixtureRoot = Assert-Child $inputRoot ([string](Get-Property $steps 'fixtureStateRoot')) 'fixture state root'
Assert-LocalPath $fixtureRoot 'fixture state root' | Out-Null

$fixtureFiles = @()
foreach ($declared in @(Get-Property $steps 'fixtureFiles')) {
    $relative = [string](Get-Property $declared 'path')
    $source = Assert-Child $fixtureRoot $relative 'fixture file'
    $item = Assert-LocalPath $source 'fixture file' $true
    $hash = Get-Hash $source
    if ($item.Length -ne 32 -or [int64](Get-Property $declared 'size') -ne 32 -or [string](Get-Property $declared 'sha256') -ne $FixtureHash -or $hash -ne $FixtureHash) { throw "fixture file identity mismatch: $relative" }
    $fixtureFiles += [ordered]@{ path = $relative; size = [int64]$item.Length; sha256 = $hash }
}

$localAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
$stateRoot = Join-Path $localAppData 'yasb-limitora'
$appRoot = Join-Path $localAppData 'Programs\yasb-limitora'
Invoke-C5Process 'install' 'install' $setupPath $SilentArguments (Split-Path -Parent $setupPath) $EvidenceRoot | Out-Null
New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
foreach ($declared in @(Get-Property $steps 'fixtureFiles')) {
    $source = Assert-Child $fixtureRoot ([string](Get-Property $declared 'path')) 'fixture file'
    $destination = Assert-Child $stateRoot ([string](Get-Property $declared 'path')) 'state fixture file'
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Force
}
$before = Invoke-Capture $capturePath 'before' $EvidenceRoot
$uninstaller = [IO.Path]::GetFullPath((Get-RegistryUninstaller))
if (-not $uninstaller.StartsWith([IO.Path]::GetFullPath($appRoot).TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'installed uninstaller escaped the application root' }
Assert-LocalPath $uninstaller 'installed uninstaller' $true | Out-Null
Invoke-C5Process 'uninstall' 'uninstall' $uninstaller $SilentArguments (Split-Path -Parent $uninstaller) $EvidenceRoot | Out-Null
$after = Invoke-Capture $capturePath 'after' $EvidenceRoot

$beforeState = Get-Property (Get-Property $before 'trees') 'state'
$afterState = Get-Property (Get-Property $after 'trees') 'state'
if ((Get-Property (Get-Property $before 'trees') 'app').present -ne $true -or (Get-Property (Get-Property $after 'trees') 'app').present -ne $false) { throw 'application removal result was unexpected' }
if ((Get-Property (Get-Property $before 'uninstallKey') 'present') -ne $true -or (Get-Property (Get-Property $after 'uninstallKey') 'present') -ne $false) { throw 'uninstall-key removal result was unexpected' }
if ((Get-Property $afterState 'present') -ne $true) { throw 'state root was deleted; preservation proof is unavailable' }
if ((ConvertTo-Json (Get-Property $beforeState 'files') -Compress) -ne (ConvertTo-Json (Get-Property $afterState 'files') -Compress)) { throw 'fixture state files were not preserved' }

$resultText = "{`n  `"schema`": `"gentle-ai.yasb-limitora.c5-result/v1`",`n  `"scenario`": `"silent-uninstall-with-state-root`",`n  `"legacyScenarioSha256`": `"$LegacyScenarioHash`",`n  `"setup`": {`"name`": `"$SetupName`", `"size`": $SetupSize, `"sha256`": `"$SetupHash`"},`n  `"silentArguments`": [`"/VERYSILENT`", `"/SUPPRESSMSGBOXES`", `"/NORESTART`"],`n  `"fixtureFiles`": [{`"path`": `"config.json`", `"size`": 32, `"sha256`": `"$FixtureHash`"}, {`"path`": `"quota-v2-cache.json`", `"size`": 32, `"sha256`": `"$FixtureHash`"}],`n  `"statePreserved`": true,`n  `"applicationRemoved`": true,`n  `"uninstallKeyRemoved`": true,`n  `"dialogAnswerAttempted`": false`n}`n"
$resultPath = Join-Path $EvidenceRoot 'c5-result.json'
[IO.File]::WriteAllText($resultPath, $resultText, [Text.UTF8Encoding]::new($false))
Write-Output "run-c5-silent-uninstall: wrote $resultPath"
exit 0
