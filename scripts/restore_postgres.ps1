[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [switch]$Clean,
    [string]$PgRestorePath = "pg_restore",
    [string]$PsqlPath = "psql"
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

$resolvedBackup = Resolve-Path -LiteralPath $BackupFile
$backupPath = $resolvedBackup.Path
$extension = [System.IO.Path]::GetExtension($backupPath).ToLowerInvariant()
$isPlainSql = $extension -eq ".sql"

if ($isPlainSql) {
    if (-not (Get-Command $PsqlPath -ErrorAction SilentlyContinue)) {
        throw "psql was not found. Install PostgreSQL client tools or pass -PsqlPath."
    }
}
else {
    if (-not (Get-Command $PgRestorePath -ErrorAction SilentlyContinue)) {
        throw "pg_restore was not found. Install PostgreSQL client tools or pass -PgRestorePath."
    }
}

$connection = Get-ConnectionSettings -Url $DatabaseUrl
if ([string]::IsNullOrWhiteSpace($connection.Database) -or [string]::IsNullOrWhiteSpace($connection.User)) {
    throw "Database name and user are required. Set DATABASE_URL or PGDATABASE/PGUSER."
}

if ($Clean -and $isPlainSql) {
    Write-Warning "The -Clean switch applies to custom-format dumps through pg_restore. For plain SQL, restore into an empty database or create the dump with clean statements."
}

$target = "$($connection.User)@$($connection.Host):$($connection.Port)/$($connection.Database)"
if (-not $PSCmdlet.ShouldProcess($target, "Restore backup $backupPath")) {
    return
}

$previousPgPassword = $env:PGPASSWORD
try {
    if (-not [string]::IsNullOrWhiteSpace($connection.Password)) {
        $env:PGPASSWORD = $connection.Password
    }

    if ($isPlainSql) {
        $arguments = @(
            "--host", $connection.Host,
            "--port", [string]$connection.Port,
            "--username", $connection.User,
            "--dbname", $connection.Database,
            "--set", "ON_ERROR_STOP=on",
            "--file", $backupPath
        )
        & $PsqlPath @arguments
    }
    else {
        $arguments = @(
            "--host", $connection.Host,
            "--port", [string]$connection.Port,
            "--username", $connection.User,
            "--dbname", $connection.Database,
            "--no-owner",
            "--exit-on-error"
        )
        if ($Clean) {
            $arguments += @("--clean", "--if-exists")
        }
        $arguments += $backupPath
        & $PgRestorePath @arguments
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Restore failed with exit code $LASTEXITCODE."
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

Write-Host "Restore completed from: $backupPath"
