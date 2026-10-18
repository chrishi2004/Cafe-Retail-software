[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ProductionEnvFile,
    [string]$PythonPath = $env:KALPVRIK_PYTHON
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $PythonPath) { $PythonPath = Join-Path $repoRoot "backend\.venv\Scripts\python.exe" }
$ProductionEnvFile = (Resolve-Path -LiteralPath $ProductionEnvFile).Path
if ($ProductionEnvFile.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Production configuration must be outside the application repository."
}
$taskScript = Join-Path $repoRoot "backend\scripts\cafe_production.py"
# The wrapper loads a durable configuration file; no credentials enter task arguments.
$runner = Join-Path (Split-Path -Parent $ProductionEnvFile) "daily-backup.ps1"
$content = '$env:KALPVRIK_ENV_FILE = ' + "'" + $ProductionEnvFile.Replace("'", "''") + "'`n" +
    '& ' + "'" + $PythonPath.Replace("'", "''") + "' '" + $taskScript.Replace("'", "''") + "' backup --reason daily`n" +
    'exit $LASTEXITCODE'
Set-Content -LiteralPath $runner -Value $content
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ('-NoProfile -NonInteractive -File "' + $runner + '"')
$trigger = New-ScheduledTaskTrigger -Daily -At "02:15"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew
# Run elevated during installation; SYSTEM runs whether or not a cashier is logged in.
Register-ScheduledTask -TaskName "Kalpvrik-Cafe-Daily-Backup" -Action $action -Trigger $trigger -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null
Write-Host "Daily backup task installed. Run and verify it once before accepting transactions."
