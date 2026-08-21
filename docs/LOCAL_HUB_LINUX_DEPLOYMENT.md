# Linux / Omarchy Local Hub Deployment

This is the preferred production profile for a dedicated or POS-combined Local Hub. It works on Omarchy/Arch because it uses standard systemd services; a minimal Debian/Ubuntu server installation is also suitable when the machine is dedicated only to server duties.

## Hardware baseline

Recommended AI-capable configuration:

- Intel Core i5 10th generation or newer, or equivalent Ryzen 5;
- 16 GB RAM works for operations, OCR and API-based AI;
- 32 GB RAM is recommended when local LLMs run alongside PostgreSQL/OCR;
- 512 GB NVMe SSD minimum; 1 TB preferred for retained source documents/models;
- Gigabit Ethernet from Local Hub to router;
- UPS protecting Hub + router/ONT;
- separate external backup target.

## Filesystem and service account

Production paths:

```text
/opt/kalpvrik                       application checkout/build
/etc/kalpvrik/local-hub.env        secrets and runtime configuration
/var/lib/kalpvrik                   backup/runtime writable storage
/var/log/kalpvrik                   application-owned logs when needed
```

Create the service account and directories:

```bash
sudo useradd --system --home /var/lib/kalpvrik --shell /usr/bin/nologin kalpvrik || true
sudo install -d -o kalpvrik -g kalpvrik -m 0750 /opt/kalpvrik /etc/kalpvrik /var/lib/kalpvrik /var/log/kalpvrik
```

Copy/clone the reviewed release into `/opt/kalpvrik`. Runtime services do not need source-write permission.

## Required packages

Install PostgreSQL server/client, Python, virtualenv/build dependencies, Node/npm and curl using the operating system package manager. On Omarchy/Arch use the corresponding `pacman` packages. Use repository-pinned Python/npm dependencies afterward.

## Backend

```bash
cd /opt/kalpvrik/backend
python -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

Create `/etc/kalpvrik/local-hub.env` with mode `0640`, owner `root:kalpvrik`.

Minimum production configuration:

```text
ENVIRONMENT=production
DEPLOYMENT_MODE=local_hub
DATABASE_URL=postgresql+psycopg://...
LOCAL_DATABASE_URL=postgresql+psycopg://...
LOCAL_BACKUP_DATABASE_URL=postgresql://...
SECRET_KEY=<strong unique production secret>
FRONTEND_ORIGIN=https://<hosted-frontend>
FRONTEND_EXTRA_ORIGINS=http://<local-ui-origin>,https://<explicit-approved-extra-origin>
CLOUD_GATEWAY_BASE_URL=https://<cloud-gateway-host>
SYNC_DEVICE_SECRET=<strong unique device secret>
SYNC_DEVICE_NAME=Local Business Hub
KALPVRIK_BACKUP_ROOT=/var/lib/kalpvrik/backups/postgres
KALPVRIK_PUBLICATION_STATE=/var/lib/kalpvrik/menu-publication-state.json
```

Use `FRONTEND_ORIGIN` and `FRONTEND_EXTRA_ORIGINS`; there is no `CORS_ORIGINS` setting in the application configuration.

Never put the environment file in git.

Apply Local Hub migrations:

```bash
cd /opt/kalpvrik/backend
set -a; source /etc/kalpvrik/local-hub.env; set +a
.venv/bin/alembic -c alembic.ini upgrade head
.venv/bin/alembic -c alembic.ini current
```

Expected release head:

```text
20260821_0019
```

## Register the Local Hub with cloud coordination

After the Supabase cloud migration is complete, temporarily provide `CLOUD_MIGRATION_DATABASE_URL` in a trusted root/operator shell or protected environment and run:

```bash
cd /opt/kalpvrik/backend
set -a; source /etc/kalpvrik/local-hub.env; set +a
export CLOUD_MIGRATION_DATABASE_URL='postgresql+psycopg://<protected-direct-supabase-url>'
.venv/bin/python -m scripts.register_cloud_device
```

The command stores only `sha256(SYNC_DEVICE_SECRET)` in cloud coordination and never prints the raw secret. By default it registers the Local Hub across its single active business group; use `--company-id`/`--branch-id` when intentionally narrowing the installation.

After registration, remove the transient direct cloud migration credential from the interactive shell if it is not otherwise required by the deployment procedure.

## Publish the first customer Cafe snapshot

The customer QR route is cloud-primary. After device registration:

```bash
cd /opt/kalpvrik/backend
set -a; source /etc/kalpvrik/local-hub.env; set +a
.venv/bin/python -m scripts.publish_cafe_menu --force
```

This publishes only sanitized menu/table/QR/availability data. Financial records, cost prices and unrestricted business data stay on the Local Hub.

Subsequent publishing is handled by `kalpvrik-menu-publish.timer`. The publisher keeps a local non-secret fingerprint and skips unchanged snapshots, so a frequent timer does not continuously create duplicate menu versions.

## Frontend

Build a local-LAN frontend separately from the hosted build so internal devices can keep working without internet:

```bash
cd /opt/kalpvrik/frontend
npm ci
VITE_OPERATIONAL_API_BASE_URL=http://kalpvrik-hub.local:8000/api \
VITE_API_BASE_URL=http://kalpvrik-hub.local:8000/api \
VITE_CLOUD_API_BASE_URL=https://<cloud-gateway-host>/api \
npm run build
```

The local build is served by `scripts/serve_spa.py` on port 4173 with SPA fallback. No secret belongs in a `VITE_*` variable.

## Install systemd units

```bash
sudo cp /opt/kalpvrik/deploy/systemd/kalpvrik-*.service /etc/systemd/system/
sudo cp /opt/kalpvrik/deploy/systemd/kalpvrik-*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kalpvrik-api.service
sudo systemctl enable --now kalpvrik-sync.service
sudo systemctl enable --now kalpvrik-frontend.service
sudo systemctl enable --now kalpvrik-backup.timer
sudo systemctl enable --now kalpvrik-menu-publish.timer
```

API/sync/frontend restart automatically. Backup/menu timers are persistent, so reboot/power recovery does not require an interactive desktop login.

Check timers:

```bash
systemctl list-timers 'kalpvrik-*'
```

## Network boundary

- Prefer a DHCP reservation/static LAN lease for the Hub.
- Prefer Ethernet from Hub to router.
- Permit local staff devices to reach only required UI/API ports.
- Keep PostgreSQL bound to localhost/private interfaces and never expose TCP 5432 to the internet.
- Expose only FastAPI through the approved authenticated HTTPS tunnel/private network for remote owner access.
- If Cloudflare Tunnel is used, run `cloudflared` as its own managed service and restrict it to the operational API origin.
- If Tailscale is used, prefer private tailnet ACLs instead of public exposure for owner-only access.

## Health check

```bash
sudo -u kalpvrik bash /opt/kalpvrik/scripts/check_local_hub.sh
```

Expected core checks:

- PostgreSQL active;
- Local Hub API active;
- sync worker active;
- local PWA active;
- HTTP health endpoint reachable;
- local UI reachable.

Also verify:

```bash
systemctl status kalpvrik-menu-publish.timer
journalctl -u kalpvrik-menu-publish.service --since today
```

A temporary cloud outage may make an individual publication service run fail; the timer retries on later activations and does not affect Local Hub POS/billing availability.

## Backups

`kalpvrik-backup.timer` runs `scripts/backup_postgres.sh`, which:

1. creates a custom-format `pg_dump`;
2. verifies the archive can be listed by `pg_restore`;
3. atomically renames the verified temporary dump;
4. writes a SHA-256 checksum;
5. applies configured retention.

A backup is not proven until restored into a disposable PostgreSQL database and critical rows/financial totals/sync tables are verified. Keep at least one copy on media independent of the Hub SSD.

## Production boot sequence

```text
Power returns
  -> PostgreSQL
  -> Local Hub FastAPI
  -> durable sync worker
  -> local React PWA
  -> menu publication timer
  -> tunnel/private access service
  -> pending cloud/local queues drain from persisted checkpoints
```

The Local Hub must not depend on a graphical login. Omarchy can still be used when the same machine also serves as the POS workstation; backend services remain system services.

## Physical release checks

Before live billing:

1. run the exact release commit and record its SHA;
2. verify Local Hub migration `20260821_0019`;
3. verify cloud migration `20260821_cloud_0003`;
4. register the Local Hub device and confirm heartbeat/writer lease;
5. force the initial Cafe menu publication and confirm a physical QR resolves through cloud;
6. reboot and confirm all Local Hub services/timers recover automatically;
7. disconnect internet but keep LAN active and confirm POS/waiter/kitchen/local billing continue;
8. reconnect and confirm queue drain/reconciliation;
9. confirm remote Super Admin works only through approved HTTPS tunnel/private network;
10. confirm TCP 5432 is not publicly reachable;
11. perform a real backup and disposable restore drill;
12. test UPS shutdown/recovery behavior;
13. complete `docs/PRODUCTION_GO_LIVE_CHECKLIST.md`.
