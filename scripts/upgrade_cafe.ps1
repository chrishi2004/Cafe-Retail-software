[CmdletBinding()]
param([string]$PythonPath = $env:KALPVRIK_PYTHON)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $PythonPath) { $PythonPath = Join-Path $repoRoot "backend\.venv\Scripts\python.exe" }
& $PythonPath (Join-Path $repoRoot "backend\scripts\cafe_production.py") upgrade
if ($LASTEXITCODE -ne 0) { throw "Upgrade refused/failed. Do not start the application until reviewed." }
