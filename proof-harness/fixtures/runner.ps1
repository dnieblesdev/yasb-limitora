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

$scenarioPath = [IO.Path]::GetFullPath($ScenarioPath)
if (-not [IO.File]::Exists($scenarioPath)) {
    throw 'scenario.json was not found'
}
$scenario = [IO.File]::ReadAllText($scenarioPath, [Text.Encoding]::UTF8) | ConvertFrom-Json
$schema = $scenario.PSObject.Properties['schema']
$scenarioId = $scenario.PSObject.Properties['scenario']
if ($null -eq $schema -or $schema.Value -ne 'gentle-ai.yasb-limitora.reusable-vm-run/v1') {
    throw 'scenario.json schema mismatch'
}
if ($null -eq $scenarioId -or [string]$scenarioId.Value -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$') {
    throw 'scenario.json scenario is unsafe or missing'
}

$artifactPath = Join-Path ([IO.Path]::GetFullPath($EvidenceRoot)) 'artifact.txt'
if (Test-Path -LiteralPath $artifactPath) {
    throw 'fixture artifact already exists; overwrite refused'
}
[IO.File]::WriteAllText($artifactPath, "reusable-vm-fixture/v1`n", [Text.UTF8Encoding]::new($false))
Write-Output "fixture-runner: wrote $artifactPath"
exit 0
