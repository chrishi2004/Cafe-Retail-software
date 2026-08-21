# Linux / Omarchy Local Hub Deployment

This is the preferred production profile for a dedicated or POS-combined Local Hub.
The design also works on Omarchy because it is systemd-based Linux; a minimal Debian/Ubuntu
installation is preferable when the machine is dedicated only to server duties.

## Hardware baseline

Recommended AI-capable configuration:

- Intel Core i5 10th generation or newer, or equivalent Ryzen 5;
- 16 GB RAM works for operational workloads, OCR and API-based AI;
- 32 GB RAM is recommended when running local LLMs alongside PostgreSQL/OCR;
- 512 GB NVMe SSD minimum; 1 TB preferred for retained source documents/models;
- Gigabit Ethernet from Local Hub to router;
- UPS protecting Hub + router/ONT;
- separate external backup target.

## Filesystem and service account

Production paths used by the supplied systemd units:

```text
/opt/kalpvrik                       application checkout/build
/etc/kalpvrik/local-hub.env        secrets and runtime configuration
/var/lib/kalpvrik                   backup/runtime writable storage
/var/log/kalpvrik                   application-owned logs when needed
```

Create a non-login service account and directories:

```bash
sudo useradd --system --home /var/lib/kalpvrik --shell /usr/bin/nologin kalpvrik || true
sudo install -d -o kalpvrik -g kalpvrik -m 0750 /opt/kalpvrik /etc/kalpvrik /var/lib/kalpvrik /var/log/kalpvrik
```

Copy/clone the verified release into `/opt/kalpvrik` and keep the directory owned by root or
a deployment administrator. Runtime services do not need source-write permission.

## Required packages

On Debian/Ubuntu-class systems install PostgreSQL, Python, build dependencies, Node/npm,
curl and PostgreSQL client utilities. On Omarchy/Arch install the equivalent packages with
pacman. Use the repository's pinned Python and npm dependencies after OS packages exist.

## Backend

```bash
cd /opt/kalpvrik/backend
python -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

Create `/etc/kalpvrik/local-hub.env` with mode `0640` and owner `root:kalpvrik`.
At minimum set the production Local Hub configuration required by `.env.example`, including:

```text
DEPLOYMENT_MODE=local_hub
LOCAL_DATABASE_URL=postgresql+psycopg://...
LOCAL_BACKUP_DATABASE_URL=postgresql://...
SECRET_KEY=<strong unique production secret>
ENVIRONMENT=production
CORS_ORIGINS=<explicit hosted/local origins>
CLOUD_GATEWAY_BASE_URL=https://<cloud-gateway>/api
SYNC_DEVICE_ID=<registered device id or approved bootstrap value>
SYNC_DEVICE_SECRET=<registered device secret>
SYNC_BUSINESS_GROUP_ID=<scope>
SYNC_COMPANY_ID=<scope when device is venture-scoped>
SYNC_BRANCH_ID=<scope when device is branch-scoped>
```

Never put the environment file in git.

Run Local Hub migrations before enabling the API:

```bash
cd /opt/kalpvrik/backend
set -a; source /etc/kalpvrik/local-hub.env; set +a
.venv/bin/alembic upgrade head
```

## Frontend

Build a local-LAN frontend separately from the hosted frontend so its operational API base
points to the Local Hub LAN address/hostname:

```bash
cd /opt/kalpvrik/frontend
npm ci
VITE_OPERATIONAL_API_BASE_URL=http://kalpvrik-hub.local:8000/api \
VITE_API_BASE_URL=http://kalpvrik-hub.local:8000/api \
npm run build
```

The local build is served by `scripts/serve_spa.py` on port 4173 with SPA fallback.
Do not place cloud/service-role secrets in `VITE_*` variables.

## Install systemd units

```bash
sudo cp /opt/kalpvrik/deploy/systemd/kalpvrik-*.service /etc/systemd/system/
sudo cp /opt/kalpvrik/deploy/systemd/kalpvrik-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kalpvrik-api.service
sudo systemctl enable --now kalpvrik-sync.service
sudo systemctl enable --now kalpvrik-frontend.service
sudo systemctl enable --now kalpvrik-backup.timer
```

The units deliberately use `Restart=always` for API/sync/frontend and a persistent timer
for backups so power loss/reboot does not require an operator to reopen terminals.

## Network boundary

- Prefer a DHCP reservation or static LAN lease for the Hub.
- Connect the Hub to the router via Ethernet.
- Permit local staff devices to reach only the required UI/API ports.
- Keep PostgreSQL bound to localhost/private interfaces and never expose TCP 5432 to the internet.
- Remote Super Admin access exposes only FastAPI through an authenticated HTTPS tunnel/private network.
- If Cloudflare Tunnel is used, run `cloudflared` as its own managed service and restrict the tunnel to the operational API origin.
- If Tailscale is used, prefer a private tailnet/ACL rather than public exposure for owner-only access.

## Health check

```bash
sudo -u kalpvrik bash /opt/kalpvrik/scripts/check_local_hub.sh
```

Expected checks:

- PostgreSQL active;
- Local Hub API active;
- sync worker active;
- local PWA active;
- HTTP health endpoint reachable;
- local UI reachable.

## Backups

The timer runs `scripts/backup_postgres.sh`, which:

1. creates a custom-format `pg_dump`;
2. verifies the archive can be listed by `pg_restore`;
3. atomically renames the verified temporary dump;
4. writes a SHA-256 checksum;
5. applies configured retention.

A backup is not considered proven until a restore is performed into a disposable PostgreSQL
database and critical row counts/financial totals/queue tables are verified.

Keep at least one backup copy on media independent of the Hub's internal SSD.

## Production boot sequence

```text
Power returns
  -> PostgreSQL service
  -> Local Hub FastAPI
  -> durable sync worker
  -> local React PWA
  -> tunnel/private access service
  -> pending cloud/local queues drain from persisted checkpoints
```

The Local Hub must not depend on an interactive desktop login. Omarchy may still be used
when the same machine doubles as the POS workstation, but the server processes remain
system services independent of the user's graphical session.

## Release checks on the physical Hub

Before live billing:

1. reboot the Hub and confirm all services recover automatically;
2. disconnect internet while leaving LAN/Wi-Fi active and confirm POS/waiter/kitchen/local billing still work;
3. reconnect internet and confirm queue drain/reconciliation;
4. confirm customer cloud QR ordering is independent of direct Local Hub reachability;
5. confirm remote Super Admin works only through the approved HTTPS tunnel/private network;
6. confirm TCP 5432 is not internet-reachable;
7. perform a real backup and disposable restore drill;
8. verify UPS shutdown/recovery behavior;
9. record the exact deployed application commit and migration heads.
