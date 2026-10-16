[CmdletBinding()]
param([Parameter(Mandatory = $true)] [string] $RepositoryRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepositoryRoot = [IO.Path]::GetFullPath($RepositoryRoot)
$gateScript = Join-Path $RepositoryRoot 'proof-harness\host\disk-binding-gate.ps1'
if (-not (Test-Path -LiteralPath $gateScript -PathType Leaf)) { throw 'disk binding gate source is missing' }
. $gateScript

$expectedCheckpointPath = 'D:\01_System_Images\Virtual_Machines\s11b-69c7ff5-20260922-050224-606df2ed\Virtual Hard Disks\os_AF76EF59-A998-4446-8A29-A065C7B90A37.avhdx'
$expectedDiskIdentifier = '3E84430E-C507-471B-8451-E41F18187D5A'
# Rotated leaf name: proves the guard no longer depends on the volatile file name.
$rotatedLeafPath = 'D:\01_System_Images\Virtual_Machines\s11b-69c7ff5-20260922-050224-606df2ed\Virtual Hard Disks\os_F9F650D6-33AC-48F3-AE03-0A795D8B125A.avhdx'

function New-Disk([hashtable] $Overrides) {
    $disk = @{ Path = $rotatedLeafPath; ControllerType = 'SCSI'; ControllerNumber = 0; ControllerLocation = 0 }
    foreach ($key in $Overrides.Keys) { $disk[$key] = $Overrides[$key] }
    return @([pscustomobject]$disk)
}
function New-Vhd([hashtable] $Overrides) {
    $vhd = @{ Path = $rotatedLeafPath; VhdType = 'Differencing'; DiskIdentifier = $expectedDiskIdentifier; ParentPath = $expectedCheckpointPath }
    foreach ($key in $Overrides.Keys) { $vhd[$key] = $Overrides[$key] }
    return [pscustomobject]$vhd
}

$script:AssertionCount = 0
$failures = [Collections.Generic.List[string]]::new()
function Assert-True([bool] $Condition, [string] $Label) {
    $script:AssertionCount++
    if (-not $Condition) { $failures.Add($Label); Write-Output ('FAIL ' + $Label) }
}

# Positive: one Differencing disk, expected DiskIdentifier, expected checkpoint ParentPath, SCSI 0:0.
$accepted = $false
try {
    [void](Assert-CurrentOsDiskBinding -Disks (New-Disk @{}) -Vhd (New-Vhd @{}) -ExpectedCheckpointPath $expectedCheckpointPath -ExpectedDiskIdentifier $expectedDiskIdentifier)
    $accepted = $true
} catch { $accepted = $false }
Assert-True $accepted 'positive rotated-leaf binding accepted'

# Negative cases: every single attribute mismatch must fail closed.
$negatives = @(
    @{ label = 'zero disks';    disks = @();                      vhd = @{} },
    @{ label = 'two disks';     disks = @(@{Path=$rotatedLeafPath;ControllerType='SCSI';ControllerNumber=0;ControllerLocation=0}, @{Path=$rotatedLeafPath;ControllerType='SCSI';ControllerNumber=0;ControllerLocation=1}); vhd = @{} },
    @{ label = 'not differencing'; disks = @{}; vhd = @{ VhdType = 'Dynamic' } },
    @{ label = 'wrong disk identifier'; disks = @{}; vhd = @{ DiskIdentifier = '00000000-0000-0000-0000-000000000000' } },
    @{ label = 'wrong parent path'; disks = @{}; vhd = @{ ParentPath = 'D:\elsewhere\os_OTHER.avhdx' } },
    @{ label = 'vhd from other disk'; disks = @{}; vhd = @{ Path = 'D:\elsewhere\os_OTHER.avhdx' } },
    @{ label = 'controller type not SCSI'; disks = @{ ControllerType = 'IDE' }; vhd = @{} },
    @{ label = 'controller number not 0'; disks = @{ ControllerNumber = 1 }; vhd = @{} },
    @{ label = 'controller location not 0'; disks = @{ ControllerLocation = 1 }; vhd = @{} }
)
foreach ($case in $negatives) {
    # @(...) preserves the empty-array case; a bare if() collapses @() to $null.
    [object[]] $disks = @(if ($case.disks -is [array]) { $case.disks } else { New-Disk $case.disks })
    $vhd = New-Vhd $case.vhd
    $threw = $false
    try {
        [void](Assert-CurrentOsDiskBinding -Disks $disks -Vhd $vhd -ExpectedCheckpointPath $expectedCheckpointPath -ExpectedDiskIdentifier $expectedDiskIdentifier)
    } catch { $threw = ($_.Exception.Message -ceq 'current-os-disk-topology-mismatch') }
    Assert-True $threw ('negative refused and named: ' + $case.label)
}

if ($failures.Count -ne 0) { Write-Output ('FAILED cases=' + ($failures -join ',')); exit 1 }
Write-Output ('PASS disk binding predicate assertions=' + $script:AssertionCount)
