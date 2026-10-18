[CmdletBinding()]
param(
    [ValidateSet("daily", "manual", "pre-upgrade")][string]$Reason = "manual",
    [string]$PythonPath = $env:KALPVRIK_PYTHON
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $PythonPath) { $PythonPath = Join-Path $repoRoot "backend\.venv\Scripts\python.exe" }
& $PythonPath (Join-Path $repoRoot "backend\scripts\cafe_production.py") backup --reason $Reason
if ($LASTEXITCODE -ne 0) { throw "Verified PostgreSQL backup failed; do not proceed with upgrade." }
