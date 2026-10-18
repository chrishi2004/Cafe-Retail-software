[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BackupFile,
    [Parameter(Mandatory = $true)][string]$ConfirmDatabase,
    [string]$TargetEnvironmentVariable = "CAFE_RESTORE_DATABASE_URL",
    [string]$PythonPath = $env:KALPVRIK_PYTHON
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $PythonPath) { $PythonPath = Join-Path $repoRoot "backend\.venv\Scripts\python.exe" }
& $PythonPath (Join-Path $repoRoot "backend\scripts\cafe_production.py") restore --archive $BackupFile --target-env $TargetEnvironmentVariable --confirm-database $ConfirmDatabase
if ($LASTEXITCODE -ne 0) { throw "Restore refused/failed. Production was not selected as a restore target." }
