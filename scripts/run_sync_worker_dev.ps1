param(
    [int]$RestartDelaySeconds = 2
)

$ErrorActionPreference = "Stop"
$BackendRoot = Join-Path $PSScriptRoot "..\backend"
$Python = Join-Path $BackendRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Backend virtual environment not found at $Python. Create backend/.venv and install requirements first."
}

Push-Location $BackendRoot
try {
    Write-Host "Starting HC1 Local Hub sync worker supervisor. Press Ctrl+C for graceful shutdown."
    while ($true) {
        & $Python -m app.sync.worker
        $exitCode = $LASTEXITCODE

        if ($exitCode -eq 0) {
            Write-Host "Sync worker exited cleanly."
            break
        }

        Write-Warning "Sync worker exited with code $exitCode. Restarting in $RestartDelaySeconds second(s)."
        Start-Sleep -Seconds $RestartDelaySeconds
    }
}
finally {
    Pop-Location
}
