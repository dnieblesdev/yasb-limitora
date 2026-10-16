# GREEN control oracle: a minimal CONFORMING lifecycle shape.
#
# Small tracked control proving the contract accepts a lifecycle that preserves the
# original exception. It is not the historical module and never shipped as one; it exists
# so the contract has a positive control that does not require owning the real lifecycle.
function Get-OwnedFailureClass([Exception]$Exception) {
    foreach ($type in @([IO.IOException],[UnauthorizedAccessException],[InvalidOperationException],[ArgumentException],[TimeoutException],[System.Security.SecurityException],[System.Management.Automation.PipelineStoppedException])) {
        if ($Exception -is $type) { return $type.Name }
    }
    return 'OtherException'
}

function Invoke-OwnedCleanupLifecycleCore($Manifest, [string]$EvidenceRoot, [Collections.IDictionary]$Services) {
    $failureStage = 'Roots'
    try {
        [void](& $Services.Roots)
    } catch {
        $originalErrorRecord = $_
        $originalException = $originalErrorRecord.Exception
        $originalClass = Get-OwnedFailureClass $originalException
        if ($originalException.Data.Contains('stage')) {
            $internalStage = [string]$originalException.Data['stage']
            if ($internalStage -in $script:OwnedFailureStages) { $failureStage = $internalStage } else { $failureStage = 'Other' }
        }
        try { if ($Services.Contains('WriteFailureDiagnostic')) { & $Services.WriteFailureDiagnostic $EvidenceRoot $failureStage $originalClass $originalException.Data $originalException $originalErrorRecord } } catch { }
        $originalException.Data['stage'] = $failureStage
        $originalException.Data['exceptionClass'] = $originalClass
        throw
    }
}
