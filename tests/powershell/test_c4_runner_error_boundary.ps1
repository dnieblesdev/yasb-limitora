[CmdletBinding()]
param([string]$RunnerPath,[string]$BaselinePath,[string]$FixtureParent)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$testStartedUtc = [DateTime]::UtcNow
if ([string]::IsNullOrWhiteSpace($RunnerPath)) { throw 'RunnerPath is required' }
if ([string]::IsNullOrWhiteSpace($BaselinePath)) { throw 'BaselinePath is required' }
if ([string]::IsNullOrWhiteSpace($FixtureParent)) { throw 'FixtureParent is required' }
$RunnerPath = [IO.Path]::GetFullPath($RunnerPath)
$baselinePath = [IO.Path]::GetFullPath($BaselinePath)
$candidatePath = $RunnerPath
$fixtureRoot = Join-Path ([IO.Path]::GetFullPath($FixtureParent)) ([Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($fixtureRoot)
$script:AssertionCount = 0
$script:ChildRecords = [Collections.Generic.List[object]]::new()
function Assert-True([bool]$Condition,[string]$Message){$script:AssertionCount++;if(-not $Condition){throw "ASSERTION FAILED: $Message"}}
function Get-Identity([string]$Path){
    $stream=[IO.File]::OpenRead($Path);$sha=[Security.Cryptography.SHA256]::Create()
    try{$digest=([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose();$stream.Dispose()}
    return [ordered]@{Path=[IO.Path]::GetFullPath($Path);Size=[int64](Get-Item -LiteralPath $Path).Length;Sha256=$digest}
}
function Write-Utf8([string]$Path,[string]$Text){[IO.File]::WriteAllText($Path,$Text,[Text.UTF8Encoding]::new($false))}
function New-RunnerCase([string]$SourceRunner,[string]$Mode,[string]$JobMode='normal',[bool]$CreateRoute=$true,[bool]$ExistingDiagnostic=$false){
    $caseRoot=Join-Path $fixtureRoot ([Guid]::NewGuid().ToString('N'));[void][IO.Directory]::CreateDirectory($caseRoot)
    $runner=Join-Path $caseRoot 'runner.ps1';[IO.File]::Copy($SourceRunner,$runner,$false)
    $evidence=Join-Path $caseRoot 'evidence';[void][IO.Directory]::CreateDirectory($evidence)
    $route=Join-Path $evidence 'owned-cleanup'
    if($CreateRoute){[void][IO.Directory]::CreateDirectory($route)}
    if($ExistingDiagnostic){Write-Utf8 (Join-Path $route 'failure-diagnostic.json') 'DO-NOT-OVERWRITE'}
    $scenario=Join-Path $caseRoot 'scenario.json';Write-Utf8 $scenario '{"fixture":"inert-local-boundary-test"}'
    Write-Utf8 (Join-Path $caseRoot 'modern-path-proof.json') '{"fixture":"manifest-reader-is-stubbed"}'
    Write-Utf8 (Join-Path $caseRoot 'control.json') (([ordered]@{mode=$Mode;jobMode=$JobMode}|ConvertTo-Json -Compress))
    $manifestStub=@'
function Read-ModernProofManifest {
 param([string]$InputRoot,[string]$ManifestPath)
 $control=ConvertFrom-Json ([IO.File]::ReadAllText((Join-Path $InputRoot 'control.json')))
 if($control.mode -eq 'manifest-failure'){throw [ArgumentException]::new("SECRET manifest reader failure`nF:/private/manifest")}
 return (ConvertFrom-Json ([IO.File]::ReadAllText((Join-Path $InputRoot 'fixture-manifest.json'))))
}
'@
    Write-Utf8 (Join-Path $caseRoot 'manifest-validation.ps1') $manifestStub
    Write-Utf8 (Join-Path $caseRoot 'job-containment.ps1') "`$c=ConvertFrom-Json ([IO.File]::ReadAllText((Join-Path `$PSScriptRoot 'control.json'))); if(`$c.jobMode -eq 'throw'){throw [UnauthorizedAccessException]::new(`"SECRET job module failure`nF:/private/job`" )}`n"
    Write-Utf8 (Join-Path $caseRoot 'uninstall-consent.ps1') '# inert consent-module fixture'
    Write-Utf8 (Join-Path $caseRoot 'capture-owned-cleanup.ps1') '# inert capture-module fixture'
    $lifecycle=@'
function New-OwnedCleanupProductionServices { param($Manifest,$EvidenceRoot) return [ordered]@{} }
function Invoke-OwnedCleanupLifecycleCore {
 param($Manifest,$EvidenceRoot,$Services)
 $control=ConvertFrom-Json ([IO.File]::ReadAllText((Join-Path (Split-Path $Manifest.Artifacts.runner.Path -Parent) 'control.json')))
 if($control.mode -eq 'success'){[IO.File]::WriteAllText((Join-Path $EvidenceRoot 'fixture-lifecycle-reached.marker'),'reached',[Text.UTF8Encoding]::new($false));return}
 $failure=[InvalidOperationException]::new("SECRET lifecycle failure`nF:/private/lifecycle")
 switch -CaseSensitive ($control.mode) {
  'valid' {$failure.Data['stage']='setup-launch';$failure.Data['exceptionClass']='UnauthorizedAccessException'}
  'invalid' {$failure.Data['stage']="Injected`nSECRET";$failure.Data['exceptionClass']='InjectedClass'}
  'array' {$failure.Data['stage']=@('setup-launch',"SECRET`nInjected");$failure.Data['exceptionClass']=@('TimeoutException','SECRET')}
  'class-only' {$failure.Data['exceptionClass']='TimeoutException'}
 }
 throw $failure
}
'@
    Write-Utf8 (Join-Path $caseRoot 'owned-cleanup-lifecycle.ps1') $lifecycle
    $artifacts=[ordered]@{
        runner=(Get-Identity $runner)
        jobModule=(Get-Identity (Join-Path $caseRoot 'job-containment.ps1'))
        consentModule=(Get-Identity (Join-Path $caseRoot 'uninstall-consent.ps1'))
        captureModule=(Get-Identity (Join-Path $caseRoot 'capture-owned-cleanup.ps1'))
        lifecycleModule=(Get-Identity (Join-Path $caseRoot 'owned-cleanup-lifecycle.ps1'))
    }
    Write-Utf8 (Join-Path $caseRoot 'fixture-manifest.json') (([ordered]@{Artifacts=$artifacts}|ConvertTo-Json -Depth 6 -Compress))
    return [pscustomobject]@{Root=$caseRoot;Runner=$runner;Evidence=$evidence;Scenario=$scenario;Route=$route;Mode=$Mode;ExistingDiagnostic=$ExistingDiagnostic;CreateRoute=$CreateRoute}
}
function Invoke-RunnerFile($Case){
    $process=New-Object System.Diagnostics.Process
    $info=New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName=Join-Path $PSHOME 'powershell.exe'
    $info.Arguments='-NoProfile -NonInteractive -File "'+$Case.Runner+'" -EvidenceRoot "'+$Case.Evidence+'" -ScenarioPath "'+$Case.Scenario+'"'
    $info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true
    $process.StartInfo=$info;$watch=[Diagnostics.Stopwatch]::StartNew()
    try{
        if(-not $process.Start()){throw 'inert runner child did not start'}
        $stdoutTask=$process.StandardOutput.ReadToEndAsync();$stderrTask=$process.StandardError.ReadToEndAsync()
        if(-not $process.WaitForExit(25000)){$process.Kill();if(-not $process.WaitForExit(5000)){throw 'inert runner child exceeded bounded containment'};throw 'inert runner child exceeded 25-second limit'}
        $process.WaitForExit() | Out-Null
        $record=[pscustomobject]@{ExitCode=[int]$process.ExitCode;Stdout=$stdoutTask.GetAwaiter().GetResult();Stderr=$stderrTask.GetAwaiter().GetResult();DurationMs=[int]$watch.ElapsedMilliseconds;Evidence=$Case.Evidence;Route=$Case.Route;Root=$Case.Root}
        $script:ChildRecords.Add($record)
        return $record
    }finally{$watch.Stop();$process.Dispose()}
}
function Assert-NoSensitiveOutput($Result,[string]$Label){
    Assert-True ($Result.Stdout -notmatch 'SECRET|F:/private|raw message|lifecycle failure|manifest reader failure|job module failure') "$Label stdout leaked sentinel"
    Assert-True ($Result.Stderr -notmatch 'SECRET|F:/private|raw message|lifecycle failure|manifest reader failure|job module failure') "$Label stderr leaked sentinel"
    Assert-True ($Result.Stderr -notmatch '[\r\n].*(Injected|SECRET)') "$Label stderr contains injected newline content"
}
function Assert-BoundarySummary($Result,[string]$Phase,[string]$Stage,[string]$Class,[string]$Persistence,[string]$Label){
    Assert-True ($Result.ExitCode -eq 1) "$Label actual process exit must be 1"
    Assert-True ([string]::IsNullOrEmpty($Result.Stdout)) "$Label failure stdout must remain empty"
    foreach($piece in @("phase=$Phase","stage=$Stage","exceptionClass=$Class","diagnostic=$Persistence")){Assert-True ($Result.Stderr.Contains($piece)) "$Label stderr missing $piece"}
    Assert-NoSensitiveOutput $Result $Label
}
function Assert-PersistedDiagnostic($Result,[string]$ExpectedStage,[string]$ExpectedClass,[string]$Label){
    $path=Join-Path $Result.Route 'failure-diagnostic.json'
    Assert-True (Test-Path -LiteralPath $path -PathType Leaf) "$Label expected persisted diagnostic is missing"
    $text=[IO.File]::ReadAllText($path)
    $record=ConvertFrom-Json $text
    Assert-True ($record.schema -ceq 'yasb-limitora.owned-cleanup-failure/v1') "$Label persisted diagnostic schema mismatch"
    Assert-True ($record.result -ceq 'failed') "$Label persisted diagnostic result mismatch"
    Assert-True ($record.stage -ceq $ExpectedStage) "$Label persisted stage mismatch; expected $ExpectedStage"
    Assert-True ($record.exceptionClass -ceq $ExpectedClass) "$Label persisted class mismatch; expected $ExpectedClass"
    $fields=@($record.PSObject.Properties | ForEach-Object {$_.Name} | Sort-Object) -join ','
    Assert-True ($fields -ceq 'exceptionClass,result,schema,stage') "$Label persisted diagnostic acquired unexpected fields"
    foreach($sentinel in @('SECRET','F:/private','raw message','lifecycle failure','manifest reader failure','job module failure','Injected')){Assert-True (-not $text.Contains($sentinel)) "$Label persisted diagnostic leaked $sentinel"}
    Assert-NoSensitiveOutput $Result $Label
}
if(-not (Test-Path -LiteralPath $baselinePath -PathType Leaf)){throw 'immutable original runner baseline is missing'}
$baselineSuccess=Invoke-RunnerFile (New-RunnerCase $baselinePath 'success')
$candidateSuccess=Invoke-RunnerFile (New-RunnerCase $candidatePath 'success')
Assert-True ($baselineSuccess.ExitCode -eq 0 -and $candidateSuccess.ExitCode -eq 0) 'baseline and candidate successful runner processes must exit 0'
Assert-True ($baselineSuccess.Stdout -ceq $candidateSuccess.Stdout) 'success stdout bytes differ between baseline and candidate'
Assert-True ($baselineSuccess.Stderr -ceq $candidateSuccess.Stderr) 'success stderr bytes differ between baseline and candidate'
Assert-True ([string]::IsNullOrEmpty($candidateSuccess.Stdout) -and [string]::IsNullOrEmpty($candidateSuccess.Stderr)) 'successful fixture runner streams must remain empty'
Assert-True (Test-Path -LiteralPath (Join-Path $candidateSuccess.Evidence 'fixture-lifecycle-reached.marker') -PathType Leaf) 'success did not reach inert lifecycle marker'
$baselineFailure=Invoke-RunnerFile (New-RunnerCase $baselinePath 'valid')
Assert-True ($baselineFailure.ExitCode -eq 1) 'baseline failure process must exit 1'
Assert-True ($baselineFailure.Stderr -ceq 'owned-cleanup lifecycle failed closed'+[Environment]::NewLine) 'baseline failure contract changed unexpectedly'
$selectedFailure=Invoke-RunnerFile (New-RunnerCase $RunnerPath 'valid')
try { Assert-BoundarySummary $selectedFailure 'lifecycle-invocation' 'setup-launch' 'UnauthorizedAccessException' 'saved' 'selected runner wrapped lifecycle failure' }
catch {
    if ([string]::Equals($RunnerPath,$baselinePath,[StringComparison]::OrdinalIgnoreCase)) { Write-Output ("RED original-runner actual-boundary mismatch startedUtc={0:o} observedUtc={1:o} elapsedMs={2} processExit={3} fixture={4}" -f $testStartedUtc,[DateTime]::UtcNow,[int]([DateTime]::UtcNow-$testStartedUtc).TotalMilliseconds,$selectedFailure.ExitCode,$selectedFailure.Root) }
    throw
}
Assert-PersistedDiagnostic $selectedFailure 'setup-launch' 'UnauthorizedAccessException' 'valid wrapped lifecycle failure'
$manifestFailure=Invoke-RunnerFile (New-RunnerCase $RunnerPath 'manifest-failure')
Assert-BoundarySummary $manifestFailure 'manifest-validation' 'Other' 'ArgumentException' 'saved' 'manifest validation failure'
Assert-PersistedDiagnostic $manifestFailure 'Other' 'ArgumentException' 'manifest validation failure'
$moduleFailure=Invoke-RunnerFile (New-RunnerCase $RunnerPath 'success' 'throw')
Assert-BoundarySummary $moduleFailure 'job-module-load' 'Other' 'UnauthorizedAccessException' 'saved' 'job module load failure'
Assert-PersistedDiagnostic $moduleFailure 'Other' 'UnauthorizedAccessException' 'job module load failure'
$invalid=Invoke-RunnerFile (New-RunnerCase $RunnerPath 'invalid')
Assert-BoundarySummary $invalid 'lifecycle-invocation' 'Other' 'OtherException' 'saved' 'invalid metadata fallback'
Assert-PersistedDiagnostic $invalid 'Other' 'OtherException' 'invalid metadata fallback'
$array=Invoke-RunnerFile (New-RunnerCase $RunnerPath 'array')
Assert-BoundarySummary $array 'lifecycle-invocation' 'Other' 'OtherException' 'saved' 'array metadata fallback'
Assert-PersistedDiagnostic $array 'Other' 'OtherException' 'array metadata fallback'
$missing=Invoke-RunnerFile (New-RunnerCase $RunnerPath 'missing')
Assert-BoundarySummary $missing 'lifecycle-invocation' 'Other' 'InvalidOperationException' 'saved' 'missing metadata fallback'
Assert-PersistedDiagnostic $missing 'Other' 'InvalidOperationException' 'missing metadata fallback'
$classOnly=Invoke-RunnerFile (New-RunnerCase $RunnerPath 'class-only')
Assert-BoundarySummary $classOnly 'lifecycle-invocation' 'Other' 'TimeoutException' 'saved' 'valid class metadata'
Assert-PersistedDiagnostic $classOnly 'Other' 'TimeoutException' 'valid class metadata'
$noRoute=Invoke-RunnerFile (New-RunnerCase $RunnerPath 'missing' 'normal' $false)
Assert-BoundarySummary $noRoute 'lifecycle-invocation' 'Other' 'InvalidOperationException' 'skipped-no-owned-route' 'missing owned route'
Assert-True (-not (Test-Path -LiteralPath (Join-Path $noRoute.Route 'failure-diagnostic.json'))) 'no-route case unexpectedly created an owned-route diagnostic'
Assert-True (-not (Test-Path -LiteralPath (Join-Path $noRoute.Evidence 'failure-diagnostic.json'))) 'no-route case created an unowned fallback diagnostic'
Assert-True (-not (Test-Path -LiteralPath $noRoute.Route)) 'no-route fixture unexpectedly created an owned-cleanup route'
$existing=Invoke-RunnerFile (New-RunnerCase $RunnerPath 'valid' 'normal' $true $true)
Assert-BoundarySummary $existing 'lifecycle-invocation' 'setup-launch' 'UnauthorizedAccessException' 'write-failed' 'CreateNew diagnostic refusal'
Assert-True ([IO.File]::ReadAllText((Join-Path $existing.Route 'failure-diagnostic.json')) -ceq 'DO-NOT-OVERWRITE') 'existing diagnostic was overwritten'
$elapsed=[DateTime]::UtcNow-$testStartedUtc
$completedUtc=[DateTime]::UtcNow
$childExits=(@($script:ChildRecords | ForEach-Object {$_.ExitCode}) -join ',')
$childDurations=(@($script:ChildRecords | ForEach-Object {$_.DurationMs}) -join ',')
Write-Output ("PASS actual runner-file boundary assertions={0} startedUtc={1:o} completedUtc={2:o} elapsedMs={3} childExits={4} childDurationsMs={5} fixtures={6}" -f $script:AssertionCount,$testStartedUtc,$completedUtc,[int]$elapsed.TotalMilliseconds,$childExits,$childDurations,$fixtureRoot)
