Set-StrictMode -Version Latest

# The leaf AVHDX file name is regenerated on every VM cycle, so it is not a
# stable identity. Bind the one attached OS disk by its stable VHD metadata
# (Differencing type, DiskIdentifier and ParentPath) plus its SCSI address.
# Every attribute is fail-closed: any single mismatch throws.
function Assert-CurrentOsDiskBinding {
    param(
        [Parameter(Mandatory = $true)] [AllowEmptyCollection()] [object[]] $Disks,
        [Parameter(Mandatory = $true)] $Vhd,
        [Parameter(Mandatory = $true)] [string] $ExpectedCheckpointPath,
        [Parameter(Mandatory = $true)] [string] $ExpectedDiskIdentifier,
        [string] $FailurePredicate = 'current-os-disk-topology-mismatch'
    )
    $diskList = @($Disks)
    if ($diskList.Count -ne 1) { throw $FailurePredicate }
    $disk = $diskList[0]
    if ([string]$disk.ControllerType -ine 'SCSI') { throw $FailurePredicate }
    if ([int]$disk.ControllerNumber -ne 0) { throw $FailurePredicate }
    if ([int]$disk.ControllerLocation -ne 0) { throw $FailurePredicate }
    if ([string]::IsNullOrEmpty([string]$disk.Path)) { throw $FailurePredicate }
    # The bound VHD metadata must belong to the one attached disk.
    if ([string]$Vhd.Path -ine [string]$disk.Path) { throw $FailurePredicate }
    if ([string]$Vhd.VhdType -ine 'Differencing') { throw $FailurePredicate }
    if ([string]$Vhd.DiskIdentifier -ine $ExpectedDiskIdentifier) { throw $FailurePredicate }
    if ([string]$Vhd.ParentPath -ine $ExpectedCheckpointPath) { throw $FailurePredicate }
    return $true
}
