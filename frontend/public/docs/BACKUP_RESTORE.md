# Backup, Restore, And Reliability Guide

This browser-accessible copy mirrors the full project guide at `docs/BACKUP_RESTORE.md`.

Core rule: the PostgreSQL database is the system of record. Power BI files and CSV exports are reporting artifacts, not backups.

## Backup Folder Convention

```text
backups/postgres/YYYY-MM/hybrid_retail_bi_YYYYMMDD_HHMMSS.dump
```

The `backups/` folder is ignored by git because backups may contain business data and password hashes.

## Recommended Backup Command

```powershell
$env:PGPASSWORD="<local-password>"
pg_dump --host localhost --port 5432 --username postgres --dbname hybrid_retail_bi --format custom --no-owner --file .\backups\postgres\2026-05\hybrid_retail_bi_20260519_213000.dump
Remove-Item Env:PGPASSWORD
```

Helper script:

```powershell
$env:DATABASE_URL="postgresql+psycopg://postgres:<local-password>@localhost:5432/hybrid_retail_bi"
.\scripts\backup_postgres.ps1
```

## Recommended Restore Command

Restore to a test database first:

```powershell
$env:PGPASSWORD="<local-password>"
createdb --host localhost --port 5432 --username postgres hybrid_retail_bi_restore_test
pg_restore --host localhost --port 5432 --username postgres --dbname hybrid_retail_bi_restore_test --no-owner --exit-on-error .\backups\postgres\2026-05\hybrid_retail_bi_20260519_213000.dump
Remove-Item Env:PGPASSWORD
```

Restore over a development database with the helper:

```powershell
.\scripts\restore_postgres.ps1 -BackupFile .\backups\postgres\2026-05\hybrid_retail_bi_20260519_213000.dump -Clean -Confirm:$false
```

## Safety Checklist

- Take a backup before migrations or seed resets.
- Test restore into a separate database.
- Keep backups and `.env` files out of git.
- Encrypt backups before moving them off-machine.
- Do not run restore from a public web request in the MVP.

Full guide: `docs/BACKUP_RESTORE.md`.
