[CmdletBinding()]
param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repoRoot "backend"
$frontendRoot = Join-Path $repoRoot "frontend"
$pythonExe = Join-Path $backendRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    throw "Backend virtual environment is missing. Run: cd backend; python -m venv .venv; .venv\Scripts\python.exe -m pip install -r requirements.txt"
}

if (-not (Test-Path (Join-Path $frontendRoot "node_modules"))) {
    throw "Frontend dependencies are missing. Run: cd frontend; npm install"
}

$database = Test-NetConnection -ComputerName "127.0.0.1" -Port 5432 -WarningAction SilentlyContinue
if (-not $database.TcpTestSucceeded) {
    throw "PostgreSQL is not reachable on 127.0.0.1:5432. Start the local PostgreSQL service before starting the Local Hub."
}

$env:DEPLOYMENT_MODE = "local_hub"
$env:FRONTEND_ORIGIN = "http://127.0.0.1:$FrontendPort"

Start-Process -FilePath $pythonExe -WorkingDirectory $backendRoot -ArgumentList @(
    "-m", "uvicorn", "operational_server:app", "--host", "127.0.0.1", "--port", "$BackendPort"
) -WindowStyle Normal

Start-Process -FilePath "npm.cmd" -WorkingDirectory $frontendRoot -ArgumentList @(
    "run", "dev", "--", "--host", "127.0.0.1", "--port", "$FrontendPort"
) -WindowStyle Normal

Write-Host "Local Hub backend: http://127.0.0.1:$BackendPort/api/health"
Write-Host "Local Hub frontend: http://127.0.0.1:$FrontendPort"
