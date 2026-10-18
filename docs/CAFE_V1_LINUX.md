# Café V1 local Linux installation

Use branch `release/cafe-v1`. This profile runs PostgreSQL, the FastAPI **Operational API**, a static server for the built React application, and the daily PostgreSQL backup timer. Internet access is needed to obtain source/dependencies during installation, not to start or operate the local Café. There is no Cloud Gateway, sync worker, menu publication, QR service, AI key or Vite development server in the runtime checklist. Their existing repository functionality is retained for future profiles.

The application and PostgreSQL listen only on loopback. Open the UI on the same Linux desktop, at **http://127.0.0.1:4173/**. This profile does not expose the counter to other computers. Do not change the listeners or enable optional workers as part of Café V1.

| Location | Purpose |
| --- | --- |
| `/opt/kalpvrik` | Replaceable, root-owned application code, Python virtual environment and React build |
| `/etc/kalpvrik/local-hub.env` | Durable production configuration/secrets; root:kalpvrik, mode 0640 |
| `/var/lib/kalpvrik` | Durable runtime data, including `backups/postgres` |
| PostgreSQL's own cluster directory | Persistent database; never put it inside `/opt/kalpvrik` |

## Fresh machine

Use a systemd Linux installation with a graphical desktop/browser. Python 3.11+, PostgreSQL server and matching `pg_dump`/`pg_restore`, Git, Python venv/pip and Node.js **22+** with npm are installation prerequisites. Node/npm are build tools only. Chromium or Chrome provides an app-mode window; Firefox/xdg-open are supported fallbacks.

For Debian/Ubuntu, install the OS packages (install Node 22+ from your approved Node package source if the distribution supplies an older version):

```bash
sudo apt-get update
sudo apt-get install git python3 python3-venv python3-pip postgresql postgresql-client nodejs npm chromium xdg-utils
python3 --version
node --version   # must be 22 or newer before prepare
pg_dump --version
sudo systemctl enable --now postgresql.service
```

On Arch/Omarchy use the equivalent packages and initialize a **new** PostgreSQL cluster using the distribution's PostgreSQL instructions before starting the service. Never run cluster initialization against an existing installation. An existing PostgreSQL cluster must be retained.

Configure PostgreSQL for private/local access before creating the application database. On a new dedicated machine, these administrator commands target the default local cluster:

```bash
sudo -u postgres psql -v ON_ERROR_STOP=1 -c "ALTER SYSTEM SET listen_addresses = 'localhost';"
sudo systemctl restart postgresql.service
sudo -u postgres psql -Atc 'SHOW listen_addresses'
sudo -u postgres createuser --pwprompt cafe_app
sudo -u postgres createdb --owner=cafe_app --encoding=UTF8 kalpvrik_cafe
```

Use a strong password. Keep `pg_hba.conf` limited to local sockets/loopback and use password authentication (SCRAM) for the app's TCP connection. Do not add network-wide `trust` entries, port-forward 5432, or publish it through a container. If another cluster/port already exists, have its administrator apply these settings to the intended cluster; restarting PostgreSQL interrupts every application using that cluster. The Café preflight checks the configured database's actual `listen_addresses` and refuses public listeners.

Install the reviewed release into the stable path:

```bash
sudo git clone --branch release/cafe-v1 https://github.com/chrishi2004/Cafe-Retail-software.git /opt/kalpvrik
sudo bash /opt/kalpvrik/scripts/install_cafe_linux.sh prepare
sudoedit /etc/kalpvrik/local-hub.env
```

`prepare` creates the service account/directories, installs Python dependencies, runs `npm ci` and a typechecked production build, installs the existing API/frontend/backup units with Café loopback drop-ins, and installs the application-menu shortcut. It does **not** start the application, bootstrap, seed or migrate. It copies the environment template only when no external file exists. Repeated prepares retain configuration, database and backups; existing app services must be stopped first, and the timer is paused while dependencies are replaced. Do not keep a development `.env` or secrets in the checkout. Runtime services cannot modify the code. Inspect operator-created systemd overrides with `systemctl cat` if reusing an older installation.

Replace the environment file's two placeholders. Generate a secret with `openssl rand -hex 32`; preserve it permanently across upgrades. URL-encode special characters in the database password. Keep `KALPVRIK_PROFILE=cafe-v1`, `ENVIRONMENT=production`, `DEPLOYMENT_MODE=local_hub`, `REQUIRE_PRIVILEGED_MFA=true`, the loopback frontend origin and empty extra origins. Do not source the environment as shell code. Cloud configuration is unnecessary.

For a **new, empty database only**, follow [first-time production bootstrap](CAFE_PRODUCTION_DATA.md#first-time-installation-only): create `/etc/kalpvrik/cafe-bootstrap.json` with the real Café, branch and owner/cashier details and run:

```bash
cd /opt/kalpvrik
sudo env KALPVRIK_ENV_FILE=/etc/kalpvrik/local-hub.env backend/.venv/bin/python backend/scripts/cafe_production.py bootstrap --config /etc/kalpvrik/cafe-bootstrap.json
```

Do not run Alembic or demo seeds before bootstrap. It creates only the real business configuration, users, payment modes and invoice sequence. It prompts for passwords and refuses existing databases. Protect the bootstrap JSON with mode 0600. Enroll the owner/admin MFA using [the existing trusted-console procedure](MFA_PRODUCTION_SETUP.md), with the external environment:

```bash
cd /opt/kalpvrik/backend
sudo env KALPVRIK_ENV_FILE=/etc/kalpvrik/local-hub.env .venv/bin/python -m scripts.bootstrap_mfa begin --email OWNER_EMAIL
# Securely save the displayed recovery codes, add the authenticator, then:
sudo env KALPVRIK_ENV_FILE=/etc/kalpvrik/local-hub.env .venv/bin/python -m scripts.bootstrap_mfa confirm --email OWNER_EMAIL --code CURRENT_TOTP
```

Activate after bootstrap/MFA (or after the guarded upgrade for an existing database):

```bash
sudo bash /opt/kalpvrik/scripts/install_cafe_linux.sh activate
sudo -u kalpvrik bash /opt/kalpvrik/scripts/check_cafe_v1.sh
```

Activation validates configuration/private PostgreSQL/current schema, disables installed sync/menu publication units, enables PostgreSQL/API/frontend/backup timer across reboot, restarts API/frontend and requires an immediate verified backup. A failed preflight or backup exits unsuccessfully; inspect/fix the error before taking sales. It never creates a database or invokes bootstrap, migration or seed commands. Existing optional feature source and unit templates remain available.

Open **Kalpvrik Café** from the desktop application menu. The launcher uses Chromium/Chrome `--app` and a separate profile under the desktop user's configuration directory; run it as the logged-in user, not root. Firefox falls back to a normal window. To add a desktop icon, copy `/usr/share/applications/kalpvrik-cafe.desktop` to your desktop and mark it trusted/allow launching using your desktop environment. Signing out of the Café user does not stop the system services or close the business day.

Before real sales: configure real menu/opening stock, test owner/cashier routing and receipt printing, complete a disposable-database restore drill, then reboot the machine and rerun the health check. No interactive shell, Vite, npm, cloud login or sync process should be needed after reboot. Hardware printer and physical reboot checks must be done on the installed device.

## Health, daily backup and logs

```bash
sudo -u kalpvrik bash /opt/kalpvrik/scripts/check_cafe_v1.sh
systemctl list-timers kalpvrik-backup.timer
journalctl -u kalpvrik-api.service -u kalpvrik-frontend.service -u kalpvrik-backup.service --since today
ss -ltn   # 5432, 8000 and 4173 must be loopback only
```

The check verifies a real PostgreSQL query, private listener, current Alembic schema/production marker; active/enabled PostgreSQL, API, frontend and backup timer; latest backup service result; HTTP `/api/health`; local UI, SPA route and compiled JS asset delivery. It exits nonzero on failure without logging connection secrets. It does not query or require cloud, sync, publication, QR or AI services. `check_local_hub.sh` also defaults to this Café check; the older broader check is explicitly selected with `KALPVRIK_PROFILE=hybrid`.

The existing timer runs at 02:15 daily with catch-up after downtime. Backups use verified custom-format `pg_dump` archives, SHA-256 checksums and manifests under `/var/lib/kalpvrik/backups/postgres`, with at least 30 days' retention. See [backup/restore procedures](CAFE_PRODUCTION_DATA.md) for verification and a restore drill into a separate disposable database. Health checks do not generate invoices, payments, backups or migrations.

Manual/pre-upgrade backup:

```bash
sudo -u kalpvrik env KALPVRIK_ENV_FILE=/etc/kalpvrik/local-hub.env bash /opt/kalpvrik/scripts/pre_upgrade_backup.sh
```

## Upgrade without resetting production data

For tagged production releases, follow [the production upgrade guide](../CAFE_UPGRADE_GUIDE.md) and use `sudo bash /opt/kalpvrik/scripts/upgrade_cafe_release.sh cafe-v1.1.0` with the actual reviewed tag. It performs the backup, pinned checkout, dependencies, forward migrations, build and health checks. The branch-based steps below are retained for the initial pre-tag development installation only; do not use `git pull` as the normal production release procedure.

Schedule downtime. Take the manual backup above **before replacing code**. Stop the API/frontend and pause the backup timer; keep PostgreSQL running:

```bash
sudo systemctl stop kalpvrik-api.service kalpvrik-frontend.service kalpvrik-backup.timer
# Install the reviewed next release's code at /opt/kalpvrik (no data/config copies).
sudo git -C /opt/kalpvrik pull --ff-only origin release/cafe-v1
sudo bash /opt/kalpvrik/scripts/install_cafe_linux.sh prepare
sudo -u kalpvrik env KALPVRIK_ENV_FILE=/etc/kalpvrik/local-hub.env bash /opt/kalpvrik/scripts/upgrade_cafe.sh
sudo bash /opt/kalpvrik/scripts/install_cafe_linux.sh activate
```

The guarded upgrade makes another verified pre-upgrade backup before Alembic `upgrade head`; failure prevents migration. Never bootstrap/seed/reset an existing database. Keep `/etc/kalpvrik`, `/var/lib/kalpvrik`, PostgreSQL and its cluster across every release. If an upgrade fails, leave the app stopped and investigate; do not automatically downgrade schema or restore over production. Follow [the data safety guide](CAFE_PRODUCTION_DATA.md#normal-application-upgrade-backup-then-alembic).

## Uninstall application code, preserve business data

Take a verified manual backup first and copy it plus sidecars to another disk. Then:

```bash
sudo bash /opt/kalpvrik/scripts/uninstall_cafe_linux.sh --remove-code
# Use --keep-code instead to retain the checkout while removing service integration.
```

This stops/disables the application units and daily backup timer, removes their unit files/Café drop-ins and launcher, and optionally removes **only `/opt/kalpvrik`**. PostgreSQL stays running/enabled. The database/roles/cluster, service account, `/etc/kalpvrik`, `/var/lib/kalpvrik` and existing backups remain. No DROP, reset, database-package uninstall or data deletion is performed. Backups stop when their application runner is uninstalled; reinstall/activate to resume them. Reinstallation uses the retained environment/database and guarded upgrade, never first-time bootstrap.
