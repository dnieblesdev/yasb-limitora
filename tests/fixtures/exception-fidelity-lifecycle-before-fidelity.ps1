# RED control oracle: the historical lifecycle behavior, reduced to its minimal shape.
#
# This is NOT the historical module and NOT its promotion. It is a small tracked control
# that reproduces only the pre-fix exception behavior the contract must reject: a failure
# raised inside the core is reclassified via $.Exception and then replaced by a
# RuntimeException fabricated from $reason. The full historical module stays an external
# manifest input and is never copied here.
function Get-OwnedFailureClass([Exception]$Exception) {
    foreach ($type in @([IO.IOException],[UnauthorizedAccessException],[InvalidOperationException],[ArgumentException],[TimeoutException],[System.Security.SecurityException],[System.Management.Automation.PipelineStoppedException])) {
        if ($Exception -is $type) { return $type.Name }
    }
    return 'OtherException'
}

function Invoke-OwnedCleanupLifecycleCore($Manifest, [string]$EvidenceRoot, [Collections.IDictionary]$Services) {
    try {
        [void](& $Services.Roots)
    } catch {
        $originalException = $_.Exception
        $originalClass = Get-OwnedFailureClass $originalException
        try { if ($Services.Contains('WriteFailureDiagnostic')) { & $Services.WriteFailureDiagnostic $EvidenceRoot 'Roots' $originalClass $originalException.Data } } catch { }
        $reason = $originalException.Message
        if ($reason -match 'MANUAL') { $reason = 'owned cleanup route requires manual consent; no automatic answer was sent' }
        $callerException = [System.Management.Automation.RuntimeException]::new($reason)
        $callerException.Data['stage'] = 'Roots'
        $callerException.Data['exceptionClass'] = $originalClass
        throw $callerException
    }
}
