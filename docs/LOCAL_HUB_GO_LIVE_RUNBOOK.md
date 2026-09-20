# Local Hub installation and release gates

Status: **not approved for full-roadmap production**. Passing host checks does not mean missing business modules are implemented. See `FULL_PRODUCT_COMPLETION_MATRIX.md`.

Target: your own Linux machine (including Omarchy), PostgreSQL, Python 3.12 and Node 22. Nothing in this guide requires hosting operational data on the development workspace. Keep PostgreSQL on loopback; expose only the API and frontend to trusted LAN clients. Remote access uses your chosen authenticated HTTPS tunnel.

## 1. Pin and prepare the release

Use a reviewed commit with passing CI, not a moving branch. Record its SHA. Install PostgreSQL server/client, Python 3.12, Node 22, Git and systemd using the target distribution's package manager. Initialize PostgreSQL according to that distribution. Create a dedicated login role and an empty owned database; do not run the application as PostgreSQL superuser.

Place the reviewed checkout at `/opt/kalpvrik`, owned by your administrator. Create service user/group `kalpvrik`, writable `/var/lib/kalpvrik` and `/var/log/kalpvrik`, and restricted `/etc/kalpvrik`. Create a Python virtual environment at `backend/.venv` and install `backend/requirements.txt`. Do not use demo seed commands on the production database.

## 2. Configure before building

Copy `backend/.env.example` to the restricted environment file `/etc/kalpvrik/local-hub.env` (root owned, group `kalpvrik`, mode 0640). Configure:

- `ENVIRONMENT=production`, `DEPLOYMENT_MODE=local_hub`, `API_DOCS_ENABLED=false`, `REQUIRE_PRIVILEGED_MFA=true`.
- `LOCAL_DATABASE_URL`: SQLAlchemy PostgreSQL URL for the dedicated local database.
- `LOCAL_BACKUP_DATABASE_URL`: matching `postgresql://` URL for PostgreSQL tools.
- `SECRET_KEY`: unique random secret, at least 32 characters. Retain it securely with recovery material; encrypted MFA secrets depend on it.
- `FRONTEND_ORIGIN` and `FRONTEND_EXTRA_ORIGINS`: exact LAN and authorized remote frontend origins.
- Cloud/device settings only with a separately provisioned cloud gateway and registered device. Never use the Local Hub database as the cloud target.

The systemd environment file and Python dotenv syntax must both accept the values; quote values containing whitespace. Do not commit this file. For trusted-console commands below, load the same environment in your shell securely, or create a restricted `backend/.env` with matching application settings.

Build frontend with **browser-reachable** addresses, not `localhost` when used from other devices:

```bash
cd /opt/kalpvrik/frontend
npm ci
VITE_OPERATIONAL_API_BASE_URL=http://YOUR_HUB_LAN_IP:8000/api \
VITE_CLOUD_API_BASE_URL=https://YOUR_CLOUD_GATEWAY/api npm run build
```

Vite embeds these addresses at build time. Changing them requires rebuilding. A remote HTTPS frontend needs an HTTPS operational tunnel URL; use a separate build if LAN and remote addresses differ. Never place server secrets in `VITE_*` values.

## 3. Migrate and create the business

With the production environment loaded:

```bash
cd /opt/kalpvrik/backend
.venv/bin/alembic upgrade head
.venv/bin/python -m scripts.bootstrap_production --name 'Your Business' --email owner@example.com --business-type cafe
.venv/bin/python -m scripts.bootstrap_mfa begin --email owner@example.com
.venv/bin/python -m scripts.bootstrap_mfa confirm --email owner@example.com --code YOUR_CURRENT_CODE
```

The password is entered interactively. Bootstrap refuses an existing operational database, disables the migration-created compatibility demo company, creates a new group/company/branch, invoice sequences and payment modes, and starts non-GST. MFA enrollment prints sensitive setup/recovery material only on your trusted console; retain it privately.

Log in as owner, select the business, enter real business/branch/tax details, create staff accounts and verify permissions. Configure catalog/menu, stock, suppliers, customers and cafe tables/QR. Do not enable GST until your registration and invoice settings are reviewed. Add subsequent ventures through the owner portal.

## 4. Start services on the actual Hub

Review `deploy/systemd/` units and paths. Copy approved units to `/etc/systemd/system/`, run `systemctl daemon-reload`, then enable/start `kalpvrik-api.service`, `kalpvrik-frontend.service` and `kalpvrik-backup.timer`. Enable sync and menu publication only after cloud/device provisioning is complete. The existing service units expect `/opt/kalpvrik/backend/.venv`.

Run `bash scripts/check_local_hub.sh` and inspect logs. Its full hybrid check expects sync running. Add firewall rules restricted to intended clients. PostgreSQL must not be internet-accessible. Confirm services recover after reboot and power interruption.

## 5. Back up and rehearse recovery

```bash
bash scripts/backup_postgres.sh
```

Keep a second copy on separate media. The included backups are not encrypted; secure the media and restrict access. Retain matching checksum sidecars and record the source commit and migration revision. Retention only removes local archives older than the configured retention period.

Create a separate, empty restore database. With `LOCAL_RESTORE_DATABASE_URL` pointing to it:

```bash
bash scripts/restore_postgres.sh /path/to/backup.dump
```

The script verifies checksum, refuses any target with existing user objects, and restores atomically. Never point it at the operational database. Compare invoice counts, totals, inventory, ledgers and sync records against the source. Record duration and acceptable data loss. For actual recovery, stop API/sync first, restore into a new database, validate, then deliberately switch configuration. Keep the previous database for rollback. Do not run two sync writers with the same device identity.

## 6. Machine-readable preflight

```bash
cd /opt/kalpvrik/backend
.venv/bin/python -m scripts.preflight_local_hub
```

Exit 0 means the **listed host checks only** passed. Exit 1 blocks release. JSON contains no connection strings or credentials. Checks cover production security, PostgreSQL role, migration heads, live business, MFA and backup age/checksum. Use `--configuration-only` before connecting a database. Save the output as release evidence.

## 7. Human acceptance (must be completed on your Hub)

- Owner, admin, manager, cashier/order taker, kitchen and analyst logins; unauthorized routes/API calls denied.
- Retail scan → quote → invoice → split/partial/credit payment → stock and customer-ledger reconciliation.
- Cafe QR → cloud request → Hub sync → staff acceptance → kitchen → served → bill request → invoice/payment → table closure.
- Retry requests and restart workers; no duplicate invoices, stock movements or payments.
- Disconnect internet while LAN remains up. Staff operations continue locally. Reconnect and reconcile cloud queues without loss or duplication.
- Print on actual A4/thermal hardware, scan labels, verify rupee symbols, tax lines, margins and cuts.
- Restore drill, reboot, backup timer, disk capacity and clock synchronization.
- Check remote HTTPS access from outside LAN and confirm there is no direct database exposure.
- Complete every blocking feature row in the full-product matrix. Obtain business-owner acceptance before admitting users.

Do not equate a passing build, mocked browser suite, or preflight with full end-to-end acceptance.
