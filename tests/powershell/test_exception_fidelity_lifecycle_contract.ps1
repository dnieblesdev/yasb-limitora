<#
Lifecycle contract: any supplied owned-cleanup lifecycle must preserve the original
exception instead of replacing it with a RuntimeException fabricated from $reason.

This is a CONTRACT test, not lifecycle ownership. The lifecycle module stays an external
input supplied through the run manifest. The test receives a lifecycle path and drives its
real Invoke-OwnedCleanupLifecycleCore with a test-owned fake service map, then inspects
what that lifecycle actually handed to its own WriteFailureDiagnostic callback and what it
rethrew.

Nothing here promotes, copies or tracks owned-cleanup-lifecycle.ps1.
#>
[CmdletBinding()]
param([Parameter(Mandatory)][string]$LifecyclePath)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$lifecyclePath = [IO.Path]::GetFullPath($LifecyclePath)
if (-not (Test-Path -LiteralPath $lifecyclePath -PathType Leaf)) { throw "lifecycle not found: $lifecyclePath" }
$script:AssertionCount = 0
function Assert-True([bool]$Condition, [string]$Message) {
    $script:AssertionCount++
    if (-not $Condition) { throw "ASSERTION FAILED: $Message" }
}

$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($lifecyclePath, [ref]$tokens, [ref]$errors)
Assert-True ($errors.Count -eq 0) 'lifecycle must parse without syntax errors'
$lifecycleText = [IO.File]::ReadAllText($lifecyclePath)

# --- Contract surface: the lifecycle must offer the core entry point --------------
$coreAst = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -ceq 'Invoke-OwnedCleanupLifecycleCore' }, $true)
Assert-True ($coreAst.Count -eq 1) 'lifecycle must define exactly one Invoke-OwnedCleanupLifecycleCore'

# --- Drive the real core with a fake service map ----------------------------------
# The injected failure occurs while resolving roots, before any installer, registry,
# PATH, Hyper-V or process work, so the original exception can be observed faithfully.
$innerFailure = [InvalidOperationException]::new('SECRET inner cause')
$originalFailure = [UnauthorizedAccessException]::new('SECRET original cause', $innerFailure)
$observed = [ordered]@{ CallbackException = $null; CallbackErrorRecord = $null; CallbackClass = $null; CallbackStage = $null; Rethrown = $null }

$services = [ordered]@{
    Roots = { throw $originalFailure }
    CreateRouteRoot = { param($EvidenceRoot) return [IO.Path]::Combine([IO.Path]::GetTempPath(), [Guid]::NewGuid().ToString('N')) }
    StartJob = { param($request) return [pscustomobject]@{} }
    WaitJob = { param($job, $deadline, $kind) return 0 }
    StopJob = { param($job, $ms) return $null }
    Capture = { param($request) return $null }
    SeedState = { param($stateRoot) return $null }
    ReadRegistration = { return $null }
    ReadSetupLog = { param($log, $deadline) return [pscustomobject]@{ HelperRefusal = $false } }
    WriteSummary = { param($root, $relative, $record) return $null }
    WriteOutcome = { param($root) return $null }
    # The observable callback: record exactly what the lifecycle hands it.
    WriteFailureDiagnostic = {
        param($evidenceRoot, $stage, $exceptionClass, $data, [System.Exception]$exception = $null, [System.Management.Automation.ErrorRecord]$errorRecord = $null)
        $observed.CallbackException = $exception
        $observed.CallbackErrorRecord = $errorRecord
        $observed.CallbackClass = $exceptionClass
        $observed.CallbackStage = $stage
    }
}
$manifest = [pscustomobject]@{
    RouteSteps = [pscustomobject]@{ timeoutSeconds = 5; executionMode = 'explicit-cli'; installTask = 'addtopath'; correctOwnedPath = $false; removePath = $true; cleanupState = $true }
    CandidateSetup = [pscustomobject]@{ Path = 'inert-not-executed' }
}
try {
    . $lifecyclePath
    Invoke-OwnedCleanupLifecycleCore $manifest ([IO.Path]::GetTempPath()) $services
    Assert-True $false 'lifecycle should have propagated its failure'
} catch {
    $observed.Rethrown = $_
}

# --- Contract assertions -----------------------------------------------------------
Assert-True ($null -ne $observed.Rethrown) 'lifecycle must rethrow a failure'
$thrown = $observed.Rethrown.Exception

# 1. Original type preserved, and no fabricated RuntimeException from $reason.
Assert-True ($thrown.GetType().FullName -ceq 'System.UnauthorizedAccessException') "lifecycle must preserve the original CLR type, got '$($thrown.GetType().FullName)'"
Assert-True ($thrown -isnot [System.Management.Automation.RuntimeException]) 'lifecycle must not substitute a fabricated RuntimeException'

# 2. Identity/semantics and inner exception.
Assert-True ([object]::ReferenceEquals($thrown, $originalFailure)) 'lifecycle must propagate the original exception object'
Assert-True ([object]::ReferenceEquals($thrown.InnerException, $innerFailure)) 'lifecycle must keep the original inner exception'
Assert-True ($thrown.Message -ceq $originalFailure.Message) 'lifecycle must not rewrite the original message'

# 3. Specific classification instead of an artificial OtherException.
# Downstream classification is what the runner computes from the propagated object; the
# tracked runner rule is replicated here so an artificial RuntimeException is caught.
function Get-ContractFailureClass([Exception]$Exception) {
    foreach ($type in @([IO.IOException],[UnauthorizedAccessException],[InvalidOperationException],[ArgumentException],[TimeoutException],[System.Security.SecurityException],[System.Management.Automation.PipelineStoppedException])) {
        if ($Exception -is $type) { return $type.Name }
    }
    return 'OtherException'
}
$downstreamClass = Get-ContractFailureClass $thrown
Assert-True ($downstreamClass -ceq 'UnauthorizedAccessException') "propagated failure must classify specifically downstream, got '$downstreamClass'"
Assert-True ($downstreamClass -cne 'OtherException') 'propagated failure must not degrade to an artificial OtherException'
Assert-True ($null -ne $observed.CallbackClass) 'lifecycle must call the failure callback'
Assert-True ($observed.CallbackClass -ceq 'UnauthorizedAccessException') "lifecycle must classify specifically, got '$($observed.CallbackClass)'"

# 4. The callback receives the original exception and its ErrorRecord context.
Assert-True ($null -ne $observed.CallbackException) 'failure callback must receive the original exception object'
Assert-True ([object]::ReferenceEquals($observed.CallbackException, $originalFailure)) 'failure callback must receive the original exception object, not a substitute'
Assert-True ($null -ne $observed.CallbackErrorRecord) 'failure callback must receive the ErrorRecord context'
# The ErrorRecord observed across an outer catch is a distinct wrapper, so identity is not
# asserted here; the required property is that the callback's ErrorRecord belongs to the
# original exception and carries observable origin context.
Assert-True ([object]::ReferenceEquals($observed.CallbackErrorRecord.Exception, $originalFailure)) 'callback ErrorRecord must belong to the original exception'
Assert-True ($observed.CallbackErrorRecord.ScriptStackTrace -ne $null -or $observed.CallbackErrorRecord.InvocationInfo -ne $null) 'ErrorRecord context must carry observable origin information'

# 5. Bare rethrow or semantically equivalent behavior: no `throw <new object>`.
$fabricated = $ast.FindAll({
        param($n)
        $n -is [System.Management.Automation.Language.ThrowStatementAst] -and $null -ne $n.Pipeline -and
        $n.Pipeline.Extent.Text -match 'RuntimeException'
    }, $true)
Assert-True ($fabricated.Count -eq 0) 'lifecycle must not throw a newly constructed RuntimeException'

# 6. The persisted schema is not modified: no record shape is fabricated here.
Assert-True (-not ($lifecycleText -match 'owned-cleanup-failure/v[2-9]')) 'lifecycle must not introduce a new diagnostic schema version'
Assert-True (-not ($lifecycleText -match "schema\s*=\s*'yasb-limitora\.owned-cleanup-failure")) 'lifecycle must not own the diagnostic record shape'

Write-Output ("PASS lifecycle contract exception fidelity assertions={0}" -f $script:AssertionCount)
