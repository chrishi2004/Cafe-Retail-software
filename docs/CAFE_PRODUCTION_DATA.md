# Café V1: persistent production data and safe upgrades

Linux installation and service activation: [Café V1 local Linux profile](CAFE_V1_LINUX.md). It uses only PostgreSQL, the Operational API, built frontend and daily backup timer.

This is the production procedure for `release/cafe-v1`. PostgreSQL is the system of record. Installing application files, building the frontend or restarting services does not create, recreate, seed or reset the database. Alembic is the only normal schema upgrade path.

## Durable layout

| Purpose | Linux / Omarchy | Windows example |
|---|---|---|
| Replaceable application code | `/opt/kalpvrik` | `C:/Kalpvrik/app` |
| Durable configuration | `/etc/kalpvrik/local-hub.env` | `C:/ProgramData/Kalpvrik/local-hub.env` |
| Production application data | `/var/lib/kalpvrik` | `C:/ProgramData/Kalpvrik` |
| Verified backups | `/var/lib/kalpvrik/backups/postgres` | `C:/ProgramData/Kalpvrik/backups/postgres` |
| PostgreSQL cluster files | Existing PostgreSQL service's persistent data directory | Existing PostgreSQL service's persistent data directory |

Keep the PostgreSQL service and its cluster directory across application installs. Do not store PostgreSQL data in the checkout or a temporary container filesystem. If PostgreSQL is containerized separately, its data must use a persistent named volume or bind mount; never remove that volume during application upgrades. This release does not require Docker.

`KALPVRIK_DATA_DIR` must be an absolute path outside the repository. An optional `KALPVRIK_BACKUP_ROOT` must be inside that data directory. Symlinks are resolved before checking these boundaries. Backups, secrets and bootstrap configuration must not be committed to Git. Restrict the data/configuration directory to the service account and administrators. Keep a separately secured/encrypted copy of the external environment file, especially `SECRET_KEY`; the database dump does not contain that application encryption key. Keep an additional copy of verified archives and their sidecars on a separate disk; a backup on the same SSD does not protect against SSD loss.

## First-time installation only

1. Install a supported PostgreSQL server and matching `pg_dump`/`pg_restore` client tools. Put the client tools on PATH for the service/scheduled-task account. Create a dedicated login and **new, empty UTF-8 database** using PostgreSQL administration tools. The application never creates or drops a database. PostgreSQL needs to be configured to start automatically.
   For a new Linux installation, the PostgreSQL administrator can provision the role/database with:

   ```bash
   sudo -u postgres createuser --pwprompt cafe_app
   sudo -u postgres createdb --owner=cafe_app --encoding=UTF8 kalpvrik_cafe
   ```

   On Windows, run the equivalent PostgreSQL client commands as the database administrator:

   ```powershell
   createuser -U postgres --pwprompt cafe_app
   createdb -U postgres --owner=cafe_app --encoding=UTF8 kalpvrik_cafe
   ```

   These are one-time administrator provisioning commands, not application-upgrade steps. The bootstrap/migration role must own the target database/schema or have the required schema-creation privileges. Keep administrator access restricted.
2. Install the reviewed application version and pinned Python dependencies into `backend/.venv`. Create the durable data/configuration directories and grant the service account access. On Linux, use the account/directory setup in `LOCAL_HUB_LINUX_DEPLOYMENT.md`.
3. Create the external environment file. Use real values, a unique strong `SECRET_KEY`, and preserve that key during upgrades because it protects MFA state. Example (not a working credential file):

   ```dotenv
   ENVIRONMENT=production
   DEPLOYMENT_MODE=local_hub
   LOCAL_DATABASE_URL=postgresql+psycopg://cafe_app:REPLACE_WITH_REAL_PASSWORD@127.0.0.1:5432/kalpvrik_cafe
   LOCAL_BACKUP_DATABASE_URL=postgresql://cafe_app:REPLACE_WITH_REAL_PASSWORD@127.0.0.1:5432/kalpvrik_cafe
   SECRET_KEY=REPLACE_WITH_A_LONG_RANDOM_SECRET
   REQUIRE_PRIVILEGED_MFA=true
   FRONTEND_ORIGIN=http://127.0.0.1:4173
   KALPVRIK_DATA_DIR=/var/lib/kalpvrik
   KALPVRIK_BACKUP_RETENTION_DAYS=30
   ```

   On Windows, set `KALPVRIK_DATA_DIR=C:/ProgramData/Kalpvrik`. Escape special characters in URL credentials using URL encoding. Backup and application URLs must identify the same host, port and database; a separate backup login is supported. Do not set SQLite as a production database: production Local Hub settings and maintenance commands refuse it.
4. Store the real first-install configuration outside the checkout, for example `/etc/kalpvrik/cafe-bootstrap.json`:

   ```json
   {
     "group_name": "Your Business Group",
     "cafe_name": "Your Cafe Name",
     "legal_name": "Your Legal Business Name",
     "company_code": "CAFE",
     "slug": "cafe",
     "branch_name": "Main Counter",
     "address": "Your address",
     "city": "Your city",
     "admin_name": "Owner Name",
     "admin_email": "owner@your-domain.example",
     "cashier_name": "Employee Name",
     "cashier_email": "cashier@your-domain.example",
     "invoice_prefix": "CAFE-"
   }
   ```

   Replace all example values. Do not put passwords in this JSON or command arguments.
5. Run bootstrap **instead of running migrations or demo seeds first**. It checks that there are no existing user tables, runs the complete Alembic chain, and configures the Café within the same PostgreSQL transaction. The historical migration placeholders are converted to the configured business; no demo trading rows are generated.

   Linux, from the application directory:

   ```bash
   export KALPVRIK_ENV_FILE=/etc/kalpvrik/local-hub.env
   backend/.venv/bin/python backend/scripts/cafe_production.py bootstrap --config /etc/kalpvrik/cafe-bootstrap.json
   ```

   Windows PowerShell, from the application directory:

   ```powershell
   $env:KALPVRIK_ENV_FILE = 'C:/ProgramData/Kalpvrik/local-hub.env'
   & backend/.venv/Scripts/python.exe backend/scripts/cafe_production.py bootstrap --config C:/ProgramData/Kalpvrik/cafe-bootstrap.json
   ```

   The command prompts for distinct admin/cashier passwords of at least 12 characters. For supervised noninteractive provisioning only, supply `CAFE_ADMIN_PASSWORD` and `CAFE_CASHIER_PASSWORD` through the process environment, then remove those variables afterward. Passwords are hashed using the existing authentication engine.
6. Bootstrap creates one real Café company, one branch, a company-wide **Admin** account for the owner, a branch-assigned **Staff** cashier, Cash/UPI/Card modes, the existing non-GST business profile and a branch invoice sequence. UPI/Card require cashier-entered references; there is no payment-terminal integration. The sequence starts at one and uses a continuous counter without an automatic annual reset. No orders, invoices, customers, sales, menu, inventory or fake stock are created. Configure the actual menu and opening stock separately.
7. Enroll the admin's MFA using the existing `backend/scripts/bootstrap_mfa.py` procedure in `MFA_PRODUCTION_SETUP.md`, with the same external environment loaded. Production admin login requires enrollment; do not weaken the production MFA setting to bypass this step. Configure and test the actual receipt printer.
8. Install daily backups below and verify the first backup and restore drill **before taking real transactions**. Start the normal API/frontend services using the external configuration. Services do not invoke bootstrap or seed scripts.

Bootstrap refuses a second run even if the database has no sales yet. It never changes an existing admin password, recreates an invoice counter or wipes data. A failed bootstrap rolls back its schema/configuration transaction, allowing a clean retry. An already installed/migrated database must use the upgrade process, not bootstrap.

## Automatic daily backup

Both existing backup entrypoints now call the same PostgreSQL-only verifier:

- `scripts/backup_postgres.sh` defaults to daily.
- `scripts/backup_postgres.ps1 -Reason daily` uses the same archive policy.

Each successful backup creates a unique custom-format `.dump`, a `.dump.sha256` checksum and a `.dump.json` manifest. Verification checks the checksum, PostgreSQL archive signature, table of contents and full archive decoding via `pg_restore` without executing SQL. A failed/partial dump is removed and cannot be reported as a successful backup. Passwords are passed through the child process environment, not command-line arguments. Live `pg_dump` uses PostgreSQL's consistent database snapshot.

Retention is **at least 30 days**. Values below 30 are rejected. Only this tool's archive/manifest/checksum sets older than the retention threshold are pruned, after a new verified backup succeeds. Existing legacy archives are not deleted automatically by the new naming policy.

Linux / Omarchy (stable code path `/opt/kalpvrik`, environment `/etc/kalpvrik/local-hub.env`):

```bash
sudo bash /opt/kalpvrik/scripts/install_daily_backup.sh
systemctl list-timers kalpvrik-backup.timer
journalctl -u kalpvrik-backup.service --since today
```

The existing systemd timer runs at 02:15 daily with a small randomized delay. `Persistent=true` catches up after downtime. Installation starts one backup immediately and fails if verification fails. Set the machine timezone appropriately. The backup service account must be able to read the environment file, execute its Python/client tools, and write `/var/lib/kalpvrik`.

Windows (run an elevated PowerShell during installation):

```powershell
$env:KALPVRIK_ENV_FILE = 'C:/ProgramData/Kalpvrik/local-hub.env'
& scripts/backup_postgres.ps1 -Reason daily
& scripts/install_daily_backup.ps1 -ProductionEnvFile $env:KALPVRIK_ENV_FILE
Start-ScheduledTask -TaskName 'Kalpvrik-Cafe-Daily-Backup'
Get-ScheduledTaskInfo -TaskName 'Kalpvrik-Cafe-Daily-Backup'
```

The task runs daily at 02:15 as SYSTEM, including when employees are logged out, and catches up when the machine becomes available. The durable runner/environment and backups remain outside the checkout. SYSTEM needs access to the configured database credentials, Python, PostgreSQL client tools and data directory. Confirm `LastTaskResult` is zero and inspect the new `.dump` and sidecars after the test run. Keep the application install path stable or reinstall the task after relocating it.

## Manual and pre-upgrade backup

Load the same external environment file using `KALPVRIK_ENV_FILE` as above.

```bash
bash scripts/backup_postgres.sh manual
bash scripts/pre_upgrade_backup.sh
```

```powershell
& scripts/backup_postgres.ps1 -Reason manual
& scripts/pre_upgrade_backup.ps1
```

The tool prints the verified archive path. Copy the archive **and both sidecars** together for off-device storage. These commands never change operational data or invoice numbers.

## Restore into a separate disposable database

Do not restore over production. Create a new, empty UTF-8 PostgreSQL database named, for example, `cafe_restore_20261018`. Use a separate target URL in the current shell, leaving `LOCAL_DATABASE_URL` unchanged:

```bash
export CAFE_RESTORE_DATABASE_URL='postgresql+psycopg://restore_user:REPLACE_PASSWORD@127.0.0.1:5432/cafe_restore_20261018'
bash scripts/restore_postgres.sh --archive /var/lib/kalpvrik/backups/postgres/YYYY-MM/ACTUAL_ARCHIVE.dump --confirm-database cafe_restore_20261018
```

```powershell
$env:CAFE_RESTORE_DATABASE_URL = 'postgresql+psycopg://restore_user:REPLACE_PASSWORD@127.0.0.1:5432/cafe_restore_20261018'
& scripts/restore_postgres.ps1 -BackupFile 'C:/ProgramData/Kalpvrik/backups/postgres/YYYY-MM/ACTUAL_ARCHIVE.dump' -ConfirmDatabase cafe_restore_20261018
```

The restore verifies the archive/checksum, requires the `cafe_restore_` naming convention and exact target-name confirmation, rejects the original/source production database name and any nonempty target, and runs `pg_restore --single-transaction --exit-on-error`. There is no `--clean`, database creation, DROP or production overwrite option. Failed restores roll back target changes.

Inspect the restored database with `psql` or a database client: verify `alembic_version`, company/branch/users, the latest invoice numbers, invoice/payment totals, inventory, closing records and the production marker. Do not connect the live billing services to the drill database. Keep production serving its original database. A real disaster-recovery cutover requires an operator-reviewed configuration/service switch to a verified replacement database; the restore tool never silently changes the live connection.

## Normal application upgrade: backup, then Alembic

1. Schedule a short maintenance window. Stop the API and any worker that writes the Local Hub database. On Linux use `systemctl stop kalpvrik-api kalpvrik-sync` if the sync worker is enabled. Stop equivalent Windows processes/services. Keep PostgreSQL running.
2. Keep the existing PostgreSQL cluster, external environment file, `SECRET_KEY`, production data directory and backups unchanged. Install the reviewed code/dependencies/build into the stable application path; do not repeat first-install bootstrap, copy a demo database, remove a database volume or run any demo seed.
3. Load `KALPVRIK_ENV_FILE` and run:

   ```bash
   backend/.venv/bin/python backend/scripts/cafe_production.py check-upgrade
   bash scripts/upgrade_cafe.sh
   ```

   ```powershell
   & backend/.venv/Scripts/python.exe backend/scripts/cafe_production.py check-upgrade
   & scripts/upgrade_cafe.ps1
   ```

   `upgrade` validates the existing Alembic revision, takes and fully verifies a **pre-upgrade backup**, then invokes Alembic `upgrade head`. If the backup fails, no migration runs. An unknown/newer database revision is refused. An existing installation is marked as production after its migration; no business configuration, users or trading rows are seeded. Maintenance commands serialize using a PostgreSQL advisory lock.
4. Check `alembic current` using the same external configuration, restart the API/frontend/workers, then check login, recent invoices, history, stock and reports. Preserve the pre-upgrade backup. Do not use `alembic stamp`, downgrade, recreate tables or reset the invoice sequence as an upgrade shortcut.

`backend/.venv/bin/python backend/scripts/cafe_production.py check-upgrade --operation reset` deliberately fails on populated databases. Supported demo seed/reset entrypoints also reject `ENVIRONMENT=production`, an installed production marker even if the environment was forgotten, or non-demo company data. Removing the production marker through its migration downgrade is refused. These controls protect the supported workflows; an administrator with direct PostgreSQL ownership can still destroy data using arbitrary SQL, so restrict that access.

Bare `alembic upgrade head` remains available for reviewed database administration, but the normal production command is the wrapper so that the required pre-upgrade backup cannot be accidentally omitted. PostgreSQL schema changes and bootstrap are transactional. Upgrades do not call `create_all`, `drop_all`, reset, database creation or seed routines.

## Validation and limits

Automated PostgreSQL tests cover clean bootstrap and repeat refusal, no fake trading rows, a real Café invoice surviving upgrade/backup/restore, prior-revision upgrade, bootstrap rollback, marker-based demo/reset refusal, failed-backup upgrade refusal, restore-to-production/nonempty-target refusal and corrupt archive rejection. Additional tests cover external paths, 30-day retention and keeping passwords out of subprocess arguments.

Opt-in integration command against a **disposable test PostgreSQL server only**:

```bash
CAFE_PRODUCTION_TEST_ADMIN_URL='postgresql+psycopg://test_admin@127.0.0.1:5432/postgres' backend/.venv/bin/python -m pytest backend/tests/test_cafe_production_ops.py -q
```

The test login needs database-create/drop privileges; test databases use unique `cafe_test_`/`cafe_restore_` names and are removed afterward. Never point this test variable at a live production server. Validation run: the full backend suite passed 256 tests (18 existing environment-dependent skips), and the final focused PostgreSQL/configuration checks were rerun after review.

Windows Task Scheduler and physical host reboot behaviour must be checked on the deployment machine; automated tests do not install tasks or services on a customer device.
