[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$RepositoryRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$RepositoryRoot=[IO.Path]::GetFullPath($RepositoryRoot)
$ownedParent=Join-Path $RepositoryRoot 'build\c4n'
if (-not $ownedParent.StartsWith($RepositoryRoot.TrimEnd('\')+'\build\',[StringComparison]::OrdinalIgnoreCase)) { throw 'fixture ownership failed' }
[void][IO.Directory]::CreateDirectory($ownedParent)
$session=Join-Path $ownedParent ([Guid]::NewGuid().ToString('N').Substring(0,8))
if (Test-Path -LiteralPath $session) { throw 'fixture session already exists' }
[void][IO.Directory]::CreateDirectory($session)
$script:AssertionCount=0
$script:ChildRecords=[Collections.Generic.List[object]]::new()
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $RepositoryRoot 'tests\powershell\test_c4_runner_error_boundary.ps1'),[ref]$tokens,[ref]$errors)
if ($errors.Count -ne 0) { throw 'fixture helper parse failed' }
foreach($name in @('Assert-True','Get-Identity','Write-Utf8','New-RunnerCase','Invoke-RunnerFile')) {
 $nodes=@($ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name},$true))
 if($nodes.Count -ne 1){throw 'fixture helper identity failed'}
 . ([scriptblock]::Create($nodes[0].Extent.Text))
}
$runner=Join-Path $RepositoryRoot 'proof-harness\guest\owned-cleanup\runner.ps1'
$failures=[Collections.Generic.List[string]]::new()
foreach($rule in @('short','near','boundary','existing-short','existing-long','locked','success')) {
 $length=if($rule -in @('boundary','existing-long')){260}elseif($rule -eq 'near'){259}else{230}
 $dummy=Join-Path (Join-Path (Join-Path (Join-Path $session ('c'*32)) 'evidence') 'owned-cleanup') 'failure-diagnostic.json'
 $padding=$length-$dummy.Length-1
 if($padding -lt 1){throw 'owned fixture parent too long'}
 $fixtureRoot=Join-Path $session ('p'*$padding)
 [void][IO.Directory]::CreateDirectory($fixtureRoot)
 $mode=if($rule -eq 'success'){'success'}else{'valid'}
 $case=New-RunnerCase $runner $mode
 $path=Join-Path $case.Route 'failure-diagnostic.json'
 if($path.Length -ne $length){throw 'fixture length mismatch'}
 $native='\\?\'+$path
 $existing=$rule -in @('existing-short','existing-long','locked')
 if($existing){[IO.File]::WriteAllText($native,'DO-NOT-OVERWRITE',[Text.UTF8Encoding]::new($false))}
 $before=@([IO.Directory]::GetFileSystemEntries('\\?\'+$case.Route))
 $handle=$null
 if($rule -eq 'locked'){$handle=[IO.File]::Open($native,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)}
 try{$result=Invoke-RunnerFile $case}finally{if($null -ne $handle){$handle.Dispose()}}
 # Record only inert child streams, not paths or exception messages.
 Write-Output ($rule+' exit='+$result.ExitCode+' stdout='+($result.Stdout|ConvertTo-Json -Compress)+' stderr='+($result.Stderr|ConvertTo-Json -Compress))
 try {
  $persistence=if($existing){'write-failed'}else{'saved'}
  $expected=if($rule -eq 'success'){''}else{'owned-cleanup lifecycle failed closed; phase=lifecycle-invocation; stage=setup-launch; exceptionClass=UnauthorizedAccessException; diagnostic='+$persistence+[Environment]::NewLine}
  Assert-True ($result.ExitCode -eq $(if($rule -eq 'success'){0}else{1})) "$rule exit"
  Assert-True ($result.Stdout -ceq '') "$rule stdout"
  Assert-True ($result.Stderr -ceq $expected) "$rule exact stderr"
  if($existing){
   Assert-True ([IO.File]::ReadAllText($native) -ceq 'DO-NOT-OVERWRITE') "$rule unchanged bytes"
   Assert-True ((@([IO.Directory]::GetFileSystemEntries('\\?\'+$case.Route)) -join '|') -ceq ($before -join '|')) "$rule unchanged directory entries"
  }elseif($rule -eq 'success'){
   Assert-True (-not [IO.File]::Exists($native)) 'success has no diagnostic'
   Assert-True ([IO.File]::ReadAllText((Join-Path $case.Evidence 'fixture-lifecycle-reached.marker')) -ceq 'reached') 'success lifecycle preserved'
  }else{
   $text=[IO.File]::ReadAllText($native)
   Assert-True ($text -ceq ('{"schema":"yasb-limitora.owned-cleanup-failure/v1","stage":"setup-launch","exceptionClass":"UnauthorizedAccessException","result":"failed"}'+"`n")) "$rule complete exact JSON"
   $record=ConvertFrom-Json $text
   Assert-True ((@($record.PSObject.Properties.Name | Sort-Object) -join ',') -ceq 'exceptionClass,result,schema,stage') "$rule four fields only"
  }
 }catch{$failures.Add($rule);Write-Output ('FAIL '+$rule)}
}
if($failures.Count -ne 0){Write-Output ('FAILED rules='+($failures -join ','));exit 1}
Write-Output ('PASS native diagnostic public boundary assertions='+$script:AssertionCount)
