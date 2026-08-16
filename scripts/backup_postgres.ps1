[CmdletBinding()]
param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot "..\backups\postgres"),
    [ValidateSet("custom", "plain")]
    [string]$Format = "custom",
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [string]$PgDumpPath = "pg_dump"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function ConvertTo-PostgresUrl {
    param([string]$Url)

    return $Url -replace "^postgresql\+psycopg2?://", "postgresql://"
}

function Get-ConnectionSettings {
    param([string]$Url)

    if ($env:PGDATABASE -and $env:PGUSER) {
        return [PSCustomObject]@{
            Host = if ($env:PGHOST) { $env:PGHOST } else { "localhost" }
            Port = if ($env:PGPORT) { [int]$env:PGPORT } else { 5432 }
            Database = $env:PGDATABASE
            User = $env:PGUSER
            Password = $env:PGPASSWORD
        }
    }

    if ([string]::IsNullOrWhiteSpace($Url)) {
        throw "Set DATABASE_URL or PGHOST/PGPORT/PGDATABASE/PGUSER before running this script."
    }

    $normalizedUrl = ConvertTo-PostgresUrl -Url $Url
    $uri = [System.Uri]$normalizedUrl
    if ($uri.Scheme -notin @("postgresql", "postgres")) {
        throw "Only PostgreSQL URLs are supported."
    }

    $user = $null
    $password = $null
    if (-not [string]::IsNullOrWhiteSpace($uri.UserInfo)) {
        $parts = $uri.UserInfo.Split([char[]]@(":"), 2)
        $user = [System.Uri]::UnescapeDataString($parts[0])
        if ($parts.Count -gt 1) {
            $password = [System.Uri]::UnescapeDataString($parts[1])
        }
    }

    return [PSCustomObject]@{
        Host = $uri.Host
        Port = if ($uri.Port -gt 0) { $uri.Port } else { 5432 }
        Database = $uri.AbsolutePath.TrimStart("/")
        User = $user
        Password = $password
    }
}

if (-not (Get-Command $PgDumpPath -ErrorAction SilentlyContinue)) {
    throw "pg_dump was not found. Install PostgreSQL client tools or pass -PgDumpPath."
}

$connection = Get-ConnectionSettings -Url $DatabaseUrl
if ([string]::IsNullOrWhiteSpace($connection.Database) -or [string]::IsNullOrWhiteSpace($connection.User)) {
    throw "Database name and user are required. Set DATABASE_URL or PGDATABASE/PGUSER."
}

$monthDirectory = Join-Path $OutputDirectory (Get-Date -Format "yyyy-MM")
New-Item -ItemType Directory -Path $monthDirectory -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$safeDatabaseName = $connection.Database -replace "[^A-Za-z0-9_.-]", "_"
$extension = if ($Format -eq "custom") { "dump" } else { "sql" }
$backupFile = Join-Path $monthDirectory "$safeDatabaseName`_$timestamp.$extension"

$arguments = @(
    "--host", $connection.Host,
    "--port", [string]$connection.Port,
    "--username", $connection.User,
    "--dbname", $connection.Database,
    "--format", $Format,
    "--file", $backupFile,
    "--no-owner"
)

$previousPgPassword = $env:PGPASSWORD
try {
    if (-not [string]::IsNullOrWhiteSpace($connection.Password)) {
        $env:PGPASSWORD = $connection.Password
    }

    & $PgDumpPath @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump failed with exit code $LASTEXITCODE."
    }
}
finally {
    if ($null -ne $previousPgPassword) {
        $env:PGPASSWORD = $previousPgPassword
    }
    else {
        Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    }
}

$hash = Get-FileHash -Algorithm SHA256 -Path $backupFile
$hashFile = "$backupFile.sha256"
Set-Content -Path $hashFile -Value "$($hash.Hash)  $(Split-Path -Leaf $backupFile)"

Write-Host "Backup created: $backupFile"
Write-Host "Checksum created: $hashFile"
