<#
A2 focused boundary proof: the real runner writer must receive the real exception
context that its own catch already holds, without changing the persisted v1 record.

Extracts the real function and the real call site from runner.ps1 with the PowerShell
AST, then executes that exact call site against a capture target. No dependency on
owned-cleanup-lifecycle.ps1 and no lifecycle, installer, VM or native execution.
#>
[CmdletBinding()]
param([string]$RunnerPath)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($RunnerPath)) { throw 'RunnerPath is required' }
$runnerPath = [IO.Path]::GetFullPath($RunnerPath)
if (-not (Test-Path -LiteralPath $runnerPath -PathType Leaf)) { throw "runner not found: $runnerPath" }
$script:AssertionCount = 0
function Assert-True([bool]$Condition, [string]$Message) {
    $script:AssertionCount++
    if (-not $Condition) { throw "ASSERTION FAILED: $Message" }
}

$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($runnerPath, [ref]$tokens, [ref]$errors)
$runnerText = [IO.File]::ReadAllText($runnerPath)
Assert-True ($errors.Count -eq 0) "runner must parse without syntax errors"

# The real writer function, as declared in the runner file.
$writerAst = $ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq 'Write-OwnedFailureDiagnostic' }, $true)
Assert-True ($writerAst.Count -eq 1) "expected exactly one real Write-OwnedFailureDiagnostic in the runner"
$writerParams = @($writerAst[0].Parameters | ForEach-Object { $_.Name.VariablePath.UserPath })
$writerText = $writerAst[0].Extent.Text

# The real call site inside the runner catch.
$callAst = $ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.CommandAst] -and $node.GetCommandName() -ceq 'Write-OwnedFailureDiagnostic' }, $true)
Assert-True ($callAst.Count -eq 1) "expected exactly one real Write-OwnedFailureDiagnostic call site"
$callElements = @($callAst[0].CommandElements | Select-Object -Skip 1 | ForEach-Object { $_.Extent.Text })
$callText = $callAst[0].Extent.Text

Write-Output ("A2 writer signature: {0}" -f ($writerText -split "`n")[0].Trim())
Write-Output ("A2 call site: {0}" -f $callText.Trim())

# --- Acceptance 1: the writer accepts optional Exception and ErrorRecord ---------
Assert-True ('Exception' -in $writerParams) "writer must accept an optional Exception parameter"
Assert-True ('ErrorRecord' -in $writerParams) "writer must accept an optional ErrorRecord parameter"

# --- Acceptance 2: the real call site forwards the live exception context --------
Assert-True ('$failureException' -in $callElements) "call site must forward the caught exception object"
# The forwarded ErrorRecord must be the real $_ from the runner's own catch: accept
# either a direct $_ or a variable the runner binds from $_ in that catch.
$errorRecordArgument = $callElements[-1]
$directRecord = ($errorRecordArgument -ceq '$_')
$boundFromCatch = $false
if (-not $directRecord -and $errorRecordArgument -match '^\$(?<name>[A-Za-z_][A-Za-z0-9_]*)$') {
    $boundFromCatch = $runnerText -match ('(?m)^\s*\$' + [regex]::Escape($Matches['name']) + '\s*=\s*\$_\s*$')
}
Assert-True ($directRecord -or $boundFromCatch) "call site must forward the ErrorRecord from the runner catch (got '$errorRecordArgument')"

# --- Acceptance 3: executing the real call site delivers the exact same objects ---
$script:Captured = $null
# A capture target with the real writer's declared parameter names, so the real call
# site is executed unmodified against it.
function Write-OwnedFailureDiagnostic {
    param([string]$RootPath, [string]$Stage, [string]$ExceptionClass, $Data, [System.Exception]$Exception, [System.Management.Automation.ErrorRecord]$ErrorRecord)
    $script:Captured = [pscustomobject]@{
        RootPath = $RootPath; Stage = $Stage; ExceptionClass = $ExceptionClass
        Data = $Data; Exception = $Exception; ErrorRecord = $ErrorRecord
    }
}
$innerFailure = [InvalidOperationException]::new('SECRET inner detail')
$outerFailure = [UnauthorizedAccessException]::new('SECRET outer detail', $innerFailure)
$failureStage = 'setup-launch'
$failureClass = 'UnauthorizedAccessException'
# Execute the real call-site statement text, inside the catch so that $_ is the
# real ErrorRecord belonging to the real caught exception object.
try { throw $outerFailure } catch {
    $caughtRecord = $_
    $caughtException = $_.Exception
    $existingRoute = [IO.Path]::GetDirectoryName($runnerPath)
    $failureException = $caughtException
    # Bind the same variable names the real call site uses, from the real ErrorRecord.
    $failureErrorRecord = $caughtRecord
    $callBlock = [ScriptBlock]::Create($callText)
    & $callBlock
}

Assert-True ($null -ne $script:Captured) "real call site did not invoke the writer"
Assert-True ([object]::ReferenceEquals($script:Captured.Exception, $caughtException)) "writer must receive the same exception object the catch captured"
Assert-True ([object]::ReferenceEquals($script:Captured.ErrorRecord, $caughtRecord)) "writer must receive the corresponding ErrorRecord"
Assert-True ($script:Captured.Exception.GetType().FullName -ceq 'System.UnauthorizedAccessException') "writer must receive the original exception type"
Assert-True ([object]::ReferenceEquals($script:Captured.Exception.InnerException, $innerFailure)) "writer must receive the intact inner exception"
Assert-True ($script:Captured.Stage -ceq $failureStage) "stage must be forwarded unchanged"
Assert-True ($script:Captured.ExceptionClass -ceq $failureClass) "exceptionClass must be forwarded unchanged"

# --- Acceptance 4: the persisted v1 projection is byte-identical ----------------
# Invoke the real writer body with and without exception context into test-owned roots
# and compare the persisted bytes.
$fixtureRoot = Join-Path ([IO.Path]::GetTempPath()) ('a2-' + [Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($fixtureRoot)
try {
    function Get-OwnedFailureClass([Exception]$Exception) { return 'OtherException' }
    $script:OwnedFailureStages = @('setup-launch', 'Other')
    function Assert-PlainPathChain([string]$Path) { return [IO.Path]::GetFullPath($Path) }
    function Assert-OwnedOutputPath([string]$Root, [string]$Path) { return $Path }
    function Assert-OwnedDiagnosticRoot([string]$RootPath) {
        $full = [IO.Path]::GetFullPath($RootPath)
        $item = Get-Item -LiteralPath $full -Force -ErrorAction Stop
        if ($item -isnot [IO.DirectoryInfo] -or $item.Name -cne 'owned-cleanup') { throw 'diagnostic root is not an existing owned-cleanup route' }
        return $full
    }
    $script:RecordWriter = [ScriptBlock]::Create($writerText)
    # Dot-source the extracted definition so the real writer replaces the capture
    # target in this scope and actually performs its own persistence.
    . $script:RecordWriter

    function New-Root([string]$name) { $p = Join-Path $fixtureRoot $name; [void][IO.Directory]::CreateDirectory((Join-Path $p 'owned-cleanup')); return (Join-Path $p 'owned-cleanup') }
    $plainRoot = New-Root 'plain'
    $richRoot = New-Root 'rich'

    $plainData = [hashtable]::new()
    $plainData['stage'] = 'setup-launch'
    $plainData['exceptionClass'] = 'UnauthorizedAccessException'
    # Baseline: the pre-A2 four-argument call shape.
    Write-OwnedFailureDiagnostic $plainRoot 'setup-launch' 'UnauthorizedAccessException' $plainData
    # With context: the widened call shape, same projection expected.
    Write-OwnedFailureDiagnostic $richRoot 'setup-launch' 'UnauthorizedAccessException' $plainData $caughtException $caughtRecord

    $plainBytes = [IO.File]::ReadAllBytes((Join-Path $plainRoot 'failure-diagnostic.json'))
    $richBytes = [IO.File]::ReadAllBytes((Join-Path $richRoot 'failure-diagnostic.json'))
    $plainText = [Text.Encoding]::UTF8.GetString($plainBytes)
    $richText = [Text.Encoding]::UTF8.GetString($richBytes)
    Assert-True ($plainText -ceq $richText) "widening the writer changed the persisted v1 bytes: '$plainText' vs '$richText'"
    $record = $richText | ConvertFrom-Json
    Assert-True ($record.schema -ceq 'yasb-limitora.owned-cleanup-failure/v1') "schema must remain v1"
    $fields = @($record.PSObject.Properties | ForEach-Object { $_.Name } | Sort-Object) -join ','
    Assert-True ($fields -ceq 'exceptionClass,result,schema,stage') "v1 must keep exactly four fields, got '$fields'"
    Assert-True ($record.result -ceq 'failed') "result must remain failed"
    Assert-True (-not $richText.Contains('SECRET')) "persisted v1 must not leak exception material"
    Assert-True ($richBytes.Length -eq $plainBytes.Length) "persisted v1 byte length must be identical"
}
finally { Remove-Item -LiteralPath $fixtureRoot -Recurse -Force -ErrorAction SilentlyContinue }

Write-Output ("PASS A2 runner boundary exception context assertions={0} signature='{1}'" -f $script:AssertionCount, ($writerText -split "`n")[0].Trim())
