[CmdletBinding()]
param([Parameter(Mandatory = $true)][string] $RepositoryRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# Historical oracle: minimal pure slices, not the operational scripts or C4 v4.
# capture-owned-cleanup.ps1: helpers + PATH/record projection + ownership return.
# owned-cleanup-lifecycle.ps1: Assert-OwnedCleanupBaseline.
# verify-owned-cleanup-evidence.ps1: Assert-EvidenceBaseline.
# capture-owned-cleanup.ps1 SHA256 c3b9e6a5a554635bb5dc8bd94f25e7d091c65ead70b5da0c953fcb2617e6d19a
# owned-cleanup-lifecycle.ps1 SHA256 3215493721516b40e4c2c1fd58450948260996dacc29d5958e2d4d1af31f963b
# verify-owned-cleanup-evidence.ps1 SHA256 54c4b8443b7bc02f811e47b8849dce74e604f8f5223c7333f7bbc1e6dbedaa38
# Oracle UTF-8/LF SHA256 6724d912d2d35f2e747df09172903b5abc679af30d3d947bb2ffa5c316f0814e
$oracleSource = @'
param($PathValue, $RecordValue, [string] $AppElement)
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
function Assert-OwnedCleanupBaseline($Capture) {
    if ($Capture.appTree.present -or $Capture.stateTree.present -or $Capture.registration.present -or $Capture.ownership.recordPresent -or [int]$Capture.ownership.appElementCount -ne 0) { throw 'baseline is not a fresh owned-cleanup fixture; refusing adoption' }
}
function Assert-EvidenceBaseline($Capture){
    if($Capture.appTree.present -or $Capture.stateTree.present -or $Capture.registration.present -or $Capture.ownership.recordPresent -or $Capture.ownership.appElementCount -ne 0){throw 'baseline evidence shows pre-existing product ownership'}
    foreach($name in @('recordValid','recordPathMatches','recordTypeMatches','recordElementMatchesExpected','appElementIsFinal')){if($Capture.ownership.$name){throw 'baseline contains an unexpected ownership fact'}}
    if($Capture.registration.installLocationMatchesExpected -or $Capture.registration.uninstallerMatchesExpected){throw 'baseline contains unexpected product registration facts'}
}
'@
$sha = [Security.Cryptography.SHA256]::Create()
try { $oracleHash = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($oracleSource.Replace("`r`n", "`n"))))).Replace('-', '').ToLowerInvariant() }
finally { $sha.Dispose() }
if ($oracleHash -cne '6724d912d2d35f2e747df09172903b5abc679af30d3d947bb2ffa5c316f0814e') { throw 'historical oracle hash mismatch' }
$oracle = [scriptblock]::Create($oracleSource)
$functions = @($oracle.Ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst]}, $true))
$runtimeText = ($functions | Where-Object Name -eq 'Assert-OwnedCleanupBaseline').Extent.Text
$offlineText = ($functions | Where-Object Name -eq 'Assert-EvidenceBaseline').Extent.Text
$runtimeOracle = [scriptblock]::Create($runtimeText + '; Assert-OwnedCleanupBaseline $args[0]')
$offlineOracle = [scriptblock]::Create($offlineText + '; Assert-EvidenceBaseline $args[0]')
$modulePath = Join-Path $RepositoryRoot 'proof-harness/contracts/owned-cleanup-baseline.ps1'
if (-not (Test-Path -LiteralPath $modulePath -PathType Leaf)) { throw 'owned-cleanup baseline contract source is missing' }
$loadOutput = @(. $modulePath)
if ($loadOutput.Count -ne 0) { throw 'contract import produced output' }
$script:assertions = 0
function Assert-Contract([bool] $Condition, [string] $Label) {
    $script:assertions++
    if (-not $Condition) { throw ('contract assertion failed: ' + $Label) }
}
function Get-Outcome([scriptblock] $Action, $InputValue) {
    try { return [ordered]@{ ok = $true; value = (& $Action $InputValue); message = '' } }
    catch { return [ordered]@{ ok = $false; value = $null; message = $_.Exception.Message } }
}
function Get-Serialized($Value) { return ConvertTo-Json -InputObject $Value -Depth 12 -Compress }
$fields = @('recordPresent','recordValid','recordPathMatches','recordTypeMatches','recordElementMatchesExpected','appElementCount','appElementIsFinal')
$app = 'C:' + [char]92 + 'FixtureApp'
$path = 'C:Other;;' + $app
$validRecord = Get-Serialized ([ordered]@{ element = $app; path = $path; type = 2 })
$cases = [Collections.Generic.List[object]]::new()
function Add-Case {
    param([string] $Name, $Raw, $Record = $null, [string] $Kind = 'ExpandString', [bool] $Present = $true, [string] $RecordKind = 'String', [bool] $RecordPresent = ($null -ne $Record))
    $cases.Add([ordered]@{ name = $Name; path = [ordered]@{present=$Present;kind=$Kind;value=$Raw}; record = [ordered]@{present=$RecordPresent;kind=$RecordKind;value=$Record} })
}
Add-Case 'clean' 'C:Other;;'
Add-Case 'path-absent' $null -Present $false
Add-Case 'contaminated-final' $path
Add-Case 'contaminated-middle' ($app + ';C:Other')
Add-Case 'valid-record' $path $validRecord
Add-Case 'invalid-json' $path '{'
Add-Case 'duplicate-elements' ($app + ';' + $app)
Add-Case 'case-insensitive-membership' $app.ToLowerInvariant()
Add-Case 'trailing-empty' ($app + ';;')
Add-Case 'empty-path' ''
Add-Case 'literal-no-expansion' ('%APP%;"' + $app + '"; ' + $app + ';' + $app + '/')
Add-Case 'path-kind-string' $path (Get-Serialized @{element=$app;path=$path;type=1}) -Kind 'String'
Add-Case 'path-kind-case' $path $validRecord -Kind 'string'
Add-Case 'unsupported-path-kind' $path -Kind 'DWord'
Add-Case 'nonstring-path' 123
Add-Case 'null-path' $null
Add-Case 'path-at-limit' ('x' * 32768)
Add-Case 'path-over-limit' ('x' * 32769)
Add-Case 'record-at-limit' $path $validRecord.PadRight(65536)
Add-Case 'record-over-limit' $path $validRecord.PadRight(65537)
Add-Case 'record-kind-case' $path $validRecord -RecordKind 'string'
Add-Case 'record-kind-wrong' $path $validRecord -RecordKind 'DWord'
Add-Case 'record-nonstring' $path 42
Add-Case 'record-present-null' $path -RecordPresent $true
Add-Case 'record-absent-with-value' $path $validRecord -RecordPresent $false
Add-Case 'record-without-path' $null $validRecord -Present $false
foreach ($json in @('null','[]','{}','{"element":"x","path":"x","type":2,"extra":0}','{"element":"x","path":"x"}','{"Element":"x","path":"x","type":2}','{"element":4,"path":"x","type":2}','{"element":"x","path":4,"type":2}','{"element":"x","path":"x","type":"2"}','{"element":"x","path":"x","type":2.5}','{"element":"x","path":"x","type":true}','{"element":"x","path":"x","type":2147483648}')) {
    Add-Case ('record-shape-' + $cases.Count) $path $json
}
foreach ($length in @(32768,32769)) {
    Add-Case ('record-element-' + $length) $path (Get-Serialized @{element=('x' * $length);path=$path;type=2})
    Add-Case ('record-path-' + $length) $path (Get-Serialized @{element=$app;path=('x' * $length);type=2})
}
Add-Case 'record-path-ordinal' $path (Get-Serialized @{element=$app.ToLowerInvariant();path=$path.ToLowerInvariant();type=2})
Add-Case 'record-type-mismatch' $path (Get-Serialized @{element=$app;path=$path;type=1})
foreach ($case in $cases) {
    $before = Get-Serialized $case
    $expected = Get-Outcome {param($item) & $oracle $item.path $item.record $app} $case
    $actual = Get-Outcome {param($item) Get-OwnedCleanupPathOwnershipFacts -PathValue $item.path -RecordValue $item.record -AppElement $app} $case
    Assert-Contract ($actual.ok -eq $expected.ok) ($case.name + ': producer decision')
    Assert-Contract ($actual.message -ceq $expected.message) ($case.name + ': producer message')
    if ($actual.ok) {
        Assert-Contract ((Get-Serialized @($actual.value.Keys)) -ceq (Get-Serialized $fields)) ($case.name + ': exact seven fields')
        foreach ($field in $fields) {
            Assert-Contract ($actual.value[$field] -ceq $expected.value[$field]) ($case.name + ': ' + $field)
            Assert-Contract ($actual.value[$field].GetType() -eq $expected.value[$field].GetType()) ($case.name + ': field type ' + $field)
        }
        $snapshot = [ordered]@{ appTree=@{present=$false}; stateTree=@{present=$false}; registration=@{present=$false;installLocationMatchesExpected=$false;uninstallerMatchesExpected=$false}; ownership=$actual.value }
        $snapshotBefore = Get-Serialized $snapshot
        foreach ($pair in @(@($runtimeOracle, {param($s) Assert-OwnedCleanupBaseline $s}), @($offlineOracle, {param($s) Assert-OwnedCleanupEvidenceBaseline $s}))) {
            $old = Get-Outcome $pair[0] $snapshot
            $new = Get-Outcome $pair[1] $snapshot
            Assert-Contract ($old.ok -eq $new.ok -and $old.message -ceq $new.message) ($case.name + ': guard decision/message')
            Assert-Contract ($null -eq $new.value) ($case.name + ': guard output silent')
        }
        Assert-Contract ((Get-Serialized $snapshot) -ceq $snapshotBefore) ($case.name + ': snapshot immutable')
    }
    Assert-Contract ((Get-Serialized $case) -ceq $before) ($case.name + ': input immutable')
}
# Move only membership into the valid-record branch to reconstruct the old defect.
# The fixed parser/guards are stored once; this is not a second maintained parser.
$membershipNode = @($oracle.Ast.FindAll({param($n) $n -is [Management.Automation.Language.IfStatementAst] -and $n.Extent.Text.StartsWith('if ($pathValue.present)') -and $n.Extent.Text.Contains('$parts =')}, $true))
Assert-Contract ($membershipNode.Count -eq 1) 'unique historical membership block'
$membership = $membershipNode[0].Extent.Text
$recordTail = '$recordElementMatches = [string]::Equals($recordElement,$appElement,[StringComparison]::OrdinalIgnoreCase)'
$oldSource = $oracleSource.Replace($membership, '').Replace($recordTail, ($recordTail + "`n" + $membership))
# Before-fix fixture SHA256 f2b5c1b792679f3188c25468b0bae072356f276d68baad525c481134020e8a0b.
# Token hash independently derived from its corresponding pure slices, ignoring
# only comments/newlines (the moved block keeps different indentation).
$tokens = $null; $parseErrors = $null
[void][Management.Automation.Language.Parser]::ParseInput($oldSource, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw 'pre-fix oracle reconstruction is malformed' }
$canonical = (@($tokens | Where-Object {$_.Kind -notin @('Comment','NewLine','EndOfInput')} | ForEach-Object {$_.Text}) -join "`n")
$sha = [Security.Cryptography.SHA256]::Create()
try { $oldHash = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($canonical)))).Replace('-', '').ToLowerInvariant() }
finally { $sha.Dispose() }
if ($oldHash -cne 'e3fafdd2f018e7dc6d80493357491d50b0be9875c6ef0e1e62ab0f5a0a4fc1e1') { throw 'pre-fix oracle provenance mismatch' }
$beforeFix = [scriptblock]::Create($oldSource)
$contamination = $cases | Where-Object name -eq 'contaminated-final'
$oldFacts = & $beforeFix $contamination.path $contamination.record $app
$newFacts = Get-OwnedCleanupPathOwnershipFacts $contamination.path $contamination.record $app
Assert-Contract (-not $oldFacts.recordPresent -and $oldFacts.appElementCount -eq 0 -and -not $oldFacts.appElementIsFinal) 'old producer hides contamination'
Assert-Contract (-not $newFacts.recordPresent -and $newFacts.appElementCount -eq 1 -and $newFacts.appElementIsFinal) 'fixed producer observes membership without ownership'
$negative = [ordered]@{appTree=@{present=$false};stateTree=@{present=$false};registration=@{present=$false;installLocationMatchesExpected=$false;uninstallerMatchesExpected=$false};ownership=$oldFacts}
Assert-Contract (Get-Outcome $runtimeOracle $negative).ok 'old facts allow runtime adoption'
Assert-Contract (Get-Outcome $offlineOracle $negative).ok 'old facts allow offline adoption'
$negative.ownership = $newFacts
Assert-Contract (-not (Get-Outcome $runtimeOracle $negative).ok) 'fixed facts refuse runtime adoption'
Assert-Contract (-not (Get-Outcome $offlineOracle $negative).ok) 'fixed facts refuse offline adoption'
# Exercise each independent predicate, including offline-only registration facts.
$guardCases = 0
foreach ($target in @('appTree.present','stateTree.present','registration.present','ownership.recordPresent','ownership.appElementCount','ownership.recordValid','ownership.recordPathMatches','ownership.recordTypeMatches','ownership.recordElementMatchesExpected','ownership.appElementIsFinal','registration.installLocationMatchesExpected','registration.uninstallerMatchesExpected')) {
    $snapshot = [ordered]@{appTree=@{present=$false};stateTree=@{present=$false};registration=@{present=$false;installLocationMatchesExpected=$false;uninstallerMatchesExpected=$false};ownership=(Get-OwnedCleanupPathOwnershipFacts @{present=$false} @{present=$false} $app)}
    $parts = $target.Split('.')
    $snapshot[$parts[0]][$parts[1]] = if ($parts[1] -eq 'appElementCount') { 1 } else { $true }
    $before = Get-Serialized $snapshot
    foreach ($pair in @(@($runtimeOracle, {param($s) Assert-OwnedCleanupBaseline $s}), @($offlineOracle, {param($s) Assert-OwnedCleanupEvidenceBaseline $s}))) {
        $old = Get-Outcome $pair[0] $snapshot
        $new = Get-Outcome $pair[1] $snapshot
        Assert-Contract ($old.ok -eq $new.ok -and $old.message -ceq $new.message) ($target + ': guards remain distinct')
    }
    Assert-Contract ((Get-Serialized $snapshot) -ceq $before) ($target + ': input immutable')
    $guardCases++
}
# Actual producer counts are integers; injected fractions pin the cast distinction.
$negative.ownership = Get-OwnedCleanupPathOwnershipFacts @{present=$false} @{present=$false} $app
$negative.ownership.appElementCount = 0.4
Assert-Contract (Get-Outcome {param($s) Assert-OwnedCleanupBaseline $s} $negative).ok 'runtime retains integer cast'
Assert-Contract (-not (Get-Outcome {param($s) Assert-OwnedCleanupEvidenceBaseline $s} $negative).ok) 'offline retains uncast comparison'
Write-Output ('PASS owned-cleanup baseline contract cases=' + $cases.Count + ' guards=' + $guardCases + ' assertions=' + $script:assertions)
