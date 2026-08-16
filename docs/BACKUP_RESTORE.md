# Backup, Restore, And Reliability Guide

This guide explains how to protect the local PostgreSQL database used by the Hybrid Retail BI system.

The system is local-first, so backup discipline matters. The main business database stays local to reduce cloud cost, but that also means the local machine needs a clear recovery path.

## What Should Be Backed Up

Back up the PostgreSQL database that stores:

- Users and roles
- Branches, products, categories, and suppliers
- Inventory and stock movements
- Sales and sale items
- Purchase orders and receiving history
- Forecasts
- AI chat history
- Audit logs

Do not rely on Power BI files or CSV exports as the main backup. They are reporting artifacts, not the system of record.

## Backup Folder Convention

Use this local folder convention:

```text
backups/
  postgres/
    YYYY-MM/
      hybrid_retail_bi_YYYYMMDD_HHMMSS.dump
      hybrid_retail_bi_YYYYMMDD_HHMMSS.dump.sha256
```

Example:

```text
backups/postgres/2026-05/hybrid_retail_bi_20260519_213000.dump
```

The `backups/` folder is ignored by git. Keep backup files off GitHub because they may contain business data, user records, password hashes, AI chat messages, and audit logs.

## Environment Variables

The app uses SQLAlchemy-style `DATABASE_URL`:

```text
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/hybrid_retail_bi
```

PostgreSQL command-line tools also understand native `PG*` variables:

```powershell
$env:PGHOST="localhost"
$env:PGPORT="5432"
$env:PGDATABASE="hybrid_retail_bi"
$env:PGUSER="postgres"
$env:PGPASSWORD="<local-password>"
```

Rules:

- Do not commit `.env` files.
- Do not paste real passwords into README files, screenshots, or terminal transcripts.
- Prefer setting secrets in the current shell or local environment manager.
- Clear `PGPASSWORD` from the shell after manual commands if it was set only for backup work.

## Recommended Backup: Custom Format

Use PostgreSQL custom format for normal backups. It works with `pg_restore`, supports selective restore options, and is better for real recovery work than plain SQL.

Manual command:

```powershell
New-Item -ItemType Directory -Path .\backups\postgres\2026-05 -Force
$env:PGPASSWORD="<local-password>"
pg_dump --host localhost --port 5432 --username postgres --dbname hybrid_retail_bi --format custom --no-owner --file .\backups\postgres\2026-05\hybrid_retail_bi_20260519_213000.dump
Remove-Item Env:PGPASSWORD
```

Using the project helper script:

```powershell
$env:DATABASE_URL="postgresql+psycopg://postgres:<local-password>@localhost:5432/hybrid_retail_bi"
.\scripts\backup_postgres.ps1
```

The script creates:

- A `.dump` file under `backups/postgres/YYYY-MM/`
- A `.sha256` checksum file beside it

Official reference: [PostgreSQL pg_dump](https://www.postgresql.org/docs/current/app-pgdump.html)

## Plain SQL Backup

Plain SQL backups are useful when you want a readable SQL file.

Manual command:

```powershell
$env:PGPASSWORD="<local-password>"
pg_dump --host localhost --port 5432 --username postgres --dbname hybrid_retail_bi --format plain --no-owner --file .\backups\postgres\2026-05\hybrid_retail_bi_20260519_213000.sql
Remove-Item Env:PGPASSWORD
```

Using the helper:

```powershell
.\scripts\backup_postgres.ps1 -Format plain
```

Plain SQL is less flexible than custom format. For regular project backups, prefer custom format.

## Restore To An Empty Database

The safest restore test is to restore into a separate throwaway database first.

Create a restore target:

```powershell
$env:PGPASSWORD="<local-password>"
createdb --host localhost --port 5432 --username postgres hybrid_retail_bi_restore_test
Remove-Item Env:PGPASSWORD
```

Restore a custom-format dump:

```powershell
$env:PGPASSWORD="<local-password>"
pg_restore --host localhost --port 5432 --username postgres --dbname hybrid_retail_bi_restore_test --no-owner --exit-on-error .\backups\postgres\2026-05\hybrid_retail_bi_20260519_213000.dump
Remove-Item Env:PGPASSWORD
```

Restore a plain SQL file:

```powershell
$env:PGPASSWORD="<local-password>"
psql --host localhost --port 5432 --username postgres --dbname hybrid_retail_bi_restore_test --set ON_ERROR_STOP=on --file .\backups\postgres\2026-05\hybrid_retail_bi_20260519_213000.sql
Remove-Item Env:PGPASSWORD
```

Official references: [PostgreSQL pg_restore](https://www.postgresql.org/docs/current/app-pgrestore.html) and [PostgreSQL psql](https://www.postgresql.org/docs/current/app-psql.html)

## Restore Over The Development Database

Restoring over an existing development database can overwrite current data. Take a fresh backup first.

Using the helper script with a custom-format dump:

```powershell
$env:DATABASE_URL="postgresql+psycopg://postgres:<local-password>@localhost:5432/hybrid_retail_bi"
.\scripts\restore_postgres.ps1 -BackupFile .\backups\postgres\2026-05\hybrid_retail_bi_20260519_213000.dump -Clean -Confirm:$false
```

The `-Clean` flag tells `pg_restore` to drop existing database objects before restoring them. Use it only when you intentionally want to replace the current schema/data.

Plain SQL restore through the helper:

```powershell
.\scripts\restore_postgres.ps1 -BackupFile .\backups\postgres\2026-05\hybrid_retail_bi_20260519_213000.sql -Confirm:$false
```

For plain SQL, restore into an empty database unless the SQL dump was created with clean statements.

## Verify A Backup

After creating a backup:

1. Confirm the backup file exists.
2. Confirm the `.sha256` file exists if using the helper script.
3. Restore into a test database.
4. Run the backend against the restored database.
5. Log in and check Overview, Inventory, Sales, Purchase Orders, Forecasting, AI Assistant, and Power BI Reports.
6. Delete the test database after verification if it is no longer needed.

Example test database cleanup:

```powershell
$env:PGPASSWORD="<local-password>"
dropdb --host localhost --port 5432 --username postgres hybrid_retail_bi_restore_test
Remove-Item Env:PGPASSWORD
```

## Scheduling Backups

For a portfolio demo, manual backups are enough. For a realistic small-business setup, schedule the backup script.

Suggested schedule:

- Daily backup after store close.
- Weekly backup copied to encrypted external storage.
- Monthly backup retained for longer-term history.

Windows Task Scheduler can run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File C:\path\to\project\scripts\backup_postgres.ps1
```

Make sure the scheduled task has access to the needed environment variables or uses a local machine secret store. Do not put a real database password directly in the task name, README, or repository scripts.

## Reliability Checklist

- Take a fresh backup before schema migrations.
- Take a fresh backup before demo data reset.
- Take a fresh backup before remote demos.
- Test restore regularly, not only after something breaks.
- Keep at least one backup copy off the main machine.
- Encrypt backups before moving them to external drives or cloud storage.
- Keep `.env` files and backup files out of git.
- Document who is allowed to restore data.
- Stop the app or avoid writes during backup if you need a quiet demo snapshot.

## Why There Is No In-App Backup Button Yet

This part intentionally documents and scripts local backup/restore instead of adding an admin API that executes shell commands.

Reason:

- Running `pg_dump` or `pg_restore` from a web request is risky.
- Restore operations can overwrite business data.
- Backup credentials should stay on the local machine, not in frontend code.
- Manual scripts are safer and clearer for the MVP.

A future production version could add an admin-only backup job runner with audit logs, filesystem allowlists, background job status, and strict server-side permissions.

## Related Docs

- [Architecture](ARCHITECTURE.md)
- [Setup Guide](SETUP_GUIDE.md)
- [Case Study](CASE_STUDY.md)
- [Demo Script](DEMO_SCRIPT.md)
- [Remote Access](REMOTE_ACCESS.md)
- [QA Checklist](QA_CHECKLIST.md)
