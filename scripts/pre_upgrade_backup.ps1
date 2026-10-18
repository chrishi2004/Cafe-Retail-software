[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "backup_postgres.ps1") -Reason "pre-upgrade"
