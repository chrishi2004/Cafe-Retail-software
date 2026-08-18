[CmdletBinding()]
param(
    [int]$BackendPort = 8000
)

$ErrorActionPreference = "Stop"
$uri = "http://127.0.0.1:$BackendPort/api/health"
$response = Invoke-RestMethod -Uri $uri -Method Get

if ($response.status -ne "healthy") {
    throw "Local Hub health check failed: status was '$($response.status)'."
}

if ($response.deployment_mode -ne "local_hub") {
    throw "Wrong deployment profile: expected local_hub, got '$($response.deployment_mode)'."
}

Write-Host ("Local Hub healthy: deployment_mode={0}, database_configured={1}" -f $response.deployment_mode, $response.database_configured)
