# Pure extraction of the historical corrected ownership projection and guards.
# Inputs are already observed values; this file performs no collection or IO.
# Field helpers retain their historical names and are implementation details.
function Get-OwnedCleanupFields {
    param($Value, [string] $Label)
    if ($null -eq $Value -or $Value -is [string] -or $Value -is [ValueType] -or $Value -is [Array]) { throw "$Label must be an object" }
    if ($Value -is [Collections.IDictionary]) { return @($Value.Keys | ForEach-Object { [string]$_ }) }
    return @($Value.PSObject.Properties | Where-Object { $_.MemberType -eq 'NoteProperty' } | ForEach-Object { $_.Name })
}

function Assert-OwnedCleanupFields {
    param($Value, [string[]] $Expected, [string] $Label)
    $actual = @(Get-OwnedCleanupFields $Value $Label)
    if ($actual.Count -ne $Expected.Count) { throw "$Label has missing or unknown fields" }
    foreach ($name in $Expected) { if ($actual -cnotcontains $name) { throw "$Label has missing or unknown fields" } }
}

function Get-OwnedCleanupValue {
    param($Value, [string] $Name)
    if ($Value -is [Collections.IDictionary]) { return $Value[$Name] }
    $property = $Value.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Get-OwnedCleanupPathOwnershipFacts {
    param($PathValue, $RecordValue, [string] $AppElement)
    $pathRaw = $null
    $pathKindNumber = 0
    if ($pathValue.present) {
        if ($pathValue.kind -notin @('String','ExpandString') -or $pathValue.value -isnot [string]) { throw 'HKCU Environment Path has an unsupported type or value' }
        $pathRaw = [string]$pathValue.value
        if ($pathRaw.Length -gt 32768) { throw 'HKCU Environment Path exceeds its observation bound' }
        $pathKindNumber = if ($pathValue.kind -ceq 'String') { 1 } else { 2 }
    }
    $recordPresent = [bool]$recordValue.present
    $recordValid = $false
    $recordPathMatches = $false
    $recordTypeMatches = $false
    $recordElementMatches = $false
    $appElementCount = 0
    $appElementIsFinal = $false
    if ($pathValue.present) {
        # PATH membership is observed independently of any ownership record. A leftover
        # element must stay visible to the baseline guard even when no record exists,
        # otherwise a contaminated baseline is adopted as a fresh fixture.
        $parts = $pathRaw.Split(';')
        $appElementCount = @($parts | Where-Object { [string]::Equals($_,$appElement,[StringComparison]::OrdinalIgnoreCase) }).Count
        $appElementIsFinal = $parts.Count -gt 0 -and [string]::Equals($parts[$parts.Count - 1],$appElement,[StringComparison]::OrdinalIgnoreCase)
    }
    if ($recordPresent -and $recordValue.kind -ceq 'String' -and $recordValue.value -is [string] -and ([string]$recordValue.value).Length -le 65536) {
        try {
            $record = ConvertFrom-Json -InputObject ([string]$recordValue.value) -ErrorAction Stop
            Assert-OwnedCleanupFields $record @('element','path','type') 'owned PATH record'
            $recordElement = Get-OwnedCleanupValue $record 'element'
            $recordPath = Get-OwnedCleanupValue $record 'path'
            $recordType = Get-OwnedCleanupValue $record 'type'
            if ($recordElement -is [string] -and $recordPath -is [string] -and (($recordType -is [int]) -or ($recordType -is [long])) -and $recordPath.Length -le 32768 -and $recordElement.Length -le 32768) {
                $recordValid = $true
                $recordPathMatches = $pathValue.present -and [string]::Equals($recordPath,$pathRaw,[StringComparison]::Ordinal)
                $recordTypeMatches = $pathValue.present -and [int]$recordType -eq $pathKindNumber
                $recordElementMatches = [string]::Equals($recordElement,$appElement,[StringComparison]::OrdinalIgnoreCase)
            }
        } catch { $recordValid = $false }
    }
    return [ordered]@{ recordPresent = $recordPresent; recordValid = $recordValid; recordPathMatches = $recordPathMatches; recordTypeMatches = $recordTypeMatches; recordElementMatchesExpected = $recordElementMatches; appElementCount = $appElementCount; appElementIsFinal = $appElementIsFinal }
}

function Assert-OwnedCleanupBaseline($Capture) {
    if ($Capture.appTree.present -or $Capture.stateTree.present -or $Capture.registration.present -or $Capture.ownership.recordPresent -or [int]$Capture.ownership.appElementCount -ne 0) { throw 'baseline is not a fresh owned-cleanup fixture; refusing adoption' }
}

function Assert-OwnedCleanupEvidenceBaseline($Capture){
    if($Capture.appTree.present -or $Capture.stateTree.present -or $Capture.registration.present -or $Capture.ownership.recordPresent -or $Capture.ownership.appElementCount -ne 0){throw 'baseline evidence shows pre-existing product ownership'}
    foreach($name in @('recordValid','recordPathMatches','recordTypeMatches','recordElementMatchesExpected','appElementIsFinal')){if($Capture.ownership.$name){throw 'baseline contains an unexpected ownership fact'}}
    if($Capture.registration.installLocationMatchesExpected -or $Capture.registration.uninstallerMatchesExpected){throw 'baseline contains unexpected product registration facts'}
}
