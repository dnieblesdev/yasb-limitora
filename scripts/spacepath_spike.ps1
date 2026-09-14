<#
spacepath_spike.ps1 - S04a read-only/disposable spike harness for design section 6.

Prepares G2a evidence capture for mechanisms M1-M8 against the real release-target
YASB installation and the S02 frozen candidate. This harness never:
  - modifies PATH (Machine/User/process) or any persisted environment variable;
  - edits, creates, or deletes YASB YAML/CSS/config content: fields that need a
    disposable target-side test widget are recorded as 'pending-manual';
  - terminates, restarts, pauses, or otherwise controls YASB or any process;
  - chooses, ranks, or recommends a mechanism: feasibility judgment and the
    single mechanism choice belong to the external G2a run; this file records.
It writes only under -EvidenceDir (disposable output; delete on rollback).

Usage (native, disposable):
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\spacepath_spike.ps1 `
    -CandidateExe <frozen yasb-limitora.exe> -YasbInstallPath <real YASB dir> `
    -YasbVersion <x.y.z> -SpacedDir <spaced dir> -ShortPathDir <8.3 dir or ''> `
    -SpaceFreeDir <space-free dir or ''> -EvidenceDir <disposable out dir>
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$CandidateExe,
    [Parameter(Mandatory)][string]$YasbInstallPath,
    [Parameter(Mandatory)][string]$YasbVersion,
    [Parameter(Mandatory)][string]$SpacedDir,
    [Parameter(Mandatory)][string]$ShortPathDir,
    [Parameter(Mandatory)][string]$SpaceFreeDir,
    [Parameter(Mandatory)][string]$EvidenceDir
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$SecretPattern = '(?i)\S*(token|password|secret|cookie|credential|api.?key|authorization)\S*'
$ExeName = 'yasb-limitora.exe'

function Read-PathState {
    return ([Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User'))
}

function Invoke-LaunchProbe([string]$RunCmd) {
    # Emulates the YASB use_shell:false parse: first whitespace token is the executable.
    $first = ($RunCmd -split ' ')[0].Trim('"')
    try {
        $info = New-Object System.Diagnostics.ProcessStartInfo
        $info.FileName = $first
        $info.UseShellExecute = $false
        $info.RedirectStandardOutput = $true
        $info.RedirectStandardError = $true
        $proc = [System.Diagnostics.Process]::Start($info)
        $stdout = $proc.StandardOutput.ReadToEnd()
        $exited = $proc.WaitForExit(60000)
        $contract = $false
        try { $doc = $stdout | ConvertFrom-Json; $contract = ($doc -is [psobject]) -and ($null -eq $doc.PSObject.Properties['version']) } catch { }
        $probe = @{ launch = 'ok'; exit_code = $(if ($exited) { $proc.ExitCode } else { 'not-exited-bounded' }); stdout_json_contract = $contract; stdout_excerpt = $stdout.Substring(0, [Math]::Min(240, $stdout.Length)) }
        $proc.Dispose()
        return $probe
    } catch {
        $message = $_.Exception.Message
        return @{ launch = 'failed'; exit_code = $null; stdout_json_contract = $false; stdout_excerpt = $message.Substring(0, [Math]::Min(240, $message.Length)) }
    }
}

$PathBefore = Read-PathState
$HarnessRevision = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash
$CandidateDigest = if (Test-Path -LiteralPath $CandidateExe -PathType Leaf) { (Get-FileHash -LiteralPath $CandidateExe -Algorithm SHA256).Hash } else { 'missing' }
$SpacedExe = Join-Path $SpacedDir $ExeName
$Mechanisms = @(
    @{ id = 'M1'; run_cmd = $ExeName; use_shell = $false; role = 'control: PATH task enabled; cannot be the integration path' },
    @{ id = 'M2'; run_cmd = $ExeName; use_shell = $false; role = 'control: expected fail with PATH unchanged; proves the no-PATH requirement' },
    @{ id = 'M3'; run_cmd = (Join-Path (Split-Path -Parent $CandidateExe) $ExeName); use_shell = $false; role = 'primary candidate: full path without spaces' },
    @{ id = 'M4'; run_cmd = ('"' + $SpacedExe + '"'); use_shell = $false; role = 'quoted full path with spaces; expected fail under split(" ")' },
    @{ id = 'M5'; run_cmd = $SpacedExe; use_shell = $false; role = 'unquoted full path with spaces; expected fail' },
    @{ id = 'M6'; run_cmd = $(if ($ShortPathDir) { Join-Path $ShortPathDir $ExeName } else { '' }); use_shell = $false; role = '8.3 short-path alias (space-free) rescue candidate; disposable arrangement' },
    @{ id = 'M7'; run_cmd = $SpacedExe; use_shell = $true; role = 'shell-enabled diagnostic only; recorded, never counts as a pass' },
    @{ id = 'M8'; run_cmd = $(if ($SpaceFreeDir) { Join-Path $SpaceFreeDir $ExeName } else { '' }); use_shell = $false; role = 'space-free relocated launcher rescue candidate; disposable arrangement' }
)
$Results = @(foreach ($mechanism in $Mechanisms) {
    $launch = if ($mechanism.use_shell -or -not $mechanism.run_cmd) {
        @{ launch = 'skipped'; exit_code = $null; stdout_json_contract = $null; stdout_excerpt = '' }
    } else { Invoke-LaunchProbe $mechanism.run_cmd }
    [pscustomobject]@{
        mechanism = $mechanism.id
        role = $mechanism.role
        run_cmd = $mechanism.run_cmd
        use_shell = $mechanism.use_shell
        yaml_quote = 'pending-manual'
        screenshot = 'pending-manual'
        child_cmdline = 'pending-manual'
        process_ancestry = 'pending-manual'
        harness_launch = $launch
    }
})
$PathAfter = Read-PathState
$Record = [pscustomobject]@{
    harness = 'spacepath_spike.ps1'
    harness_revision = $HarnessRevision
    candidate_exe = $CandidateExe
    candidate_sha256 = $CandidateDigest
    yasb_version = $YasbVersion
    yasb_install_path = $YasbInstallPath
    path_before = $PathBefore
    path_after = $PathAfter
    path_unchanged_by_harness = ($PathBefore -ceq $PathAfter)
    mechanisms = $Results
    secret_scan = 'applied-before-retention'
}
$json = $Record | ConvertTo-Json -Depth 6
$hits = [regex]::Matches($json, $SecretPattern)
$redacted = [regex]::Replace($json, $SecretPattern, '<redacted>')
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$utf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText((Join-Path $EvidenceDir 'spike-evidence.json'), $redacted, $utf8)
[IO.File]::WriteAllText((Join-Path $EvidenceDir 'secret-scan.txt'), "secret_scan_matches=$($hits.Count)`nredacted=$($hits.Count -gt 0)`n", $utf8)
Write-Output "spike evidence prepared under $EvidenceDir for M1-M8; feasibility judgment and the single mechanism choice belong to external G2a"
