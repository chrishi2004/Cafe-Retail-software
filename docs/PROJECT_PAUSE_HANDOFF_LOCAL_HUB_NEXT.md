# Project Pause Handoff — Local Hub First, Then Production Setup

Status date: 2026-08-21

This document is the restart point for the next development/deployment session. The application architecture and release code are considered complete for the current release. Do not start another feature-development phase before completing the Local Hub and production-environment setup described below.

## 1. Canonical release state

Repository: `chrishi2004/Cafe-Retail-software`

Current `main` release merge:

```text
c574fdf6946bb01b8d9ae65d990cb3423c6ccfb7
```

Release PR:

```text
#10 — Release: production readiness finalization
Status: merged
```

The release branch passed all 16 GitHub verification workflows before merge, including the unified `Release Readiness` gate.

Verified repository-side gates include:

- local and cloud migrations;
- full backend regression;
- cloud/local authority isolation;
- customer QR ordering and convergence;
- Cafe billing idempotency and stock safety;
- MFA/TOTP and recovery-code behavior;
- cross-venture/business-group isolation;
- frontend typecheck/build;
- Chromium browser smoke;
- production npm dependency audit;
- Python dependency audit;
- Linux deployment script validation;
- PostgreSQL backup/checksum/restore rehearsal.

## 2. Production deployment status at pause

### Frontend

```text
Vercel project: cafe-retail-software
Status: GREEN / deployed from main
```

### Cloud API

```text
Vercel project: cafe-retail-api
Code/release preview: verified and previously Ready
Current main production deployment: blocked by Vercel free-tier deployment quota
Reason: api-deployments-free-per-day / build-rate-limit
```

This is a provider quota issue, not a known application build failure. Do not change application source merely to force another Vercel deployment.

A deployment watch may be active externally; when resuming, check `main` production status again before making any code change.

## 3. Frozen architecture contract

Do not redesign this boundary during Local Hub setup.

```text
CUSTOMER QR
  -> Hosted React frontend
  -> Restricted Cloud Gateway
  -> Supabase coordination database
  -> durable cloud/local synchronization
  -> Local Hub

POS / WAITER / KITCHEN / MANAGER
  -> Local Hub FastAPI
  -> Local PostgreSQL

REMOTE SUPER ADMIN
  -> Hosted UI
  -> authenticated HTTPS tunnel/private network
  -> Local Hub FastAPI
  -> Local PostgreSQL

FINAL FINANCIAL / STOCK AUTHORITY
  -> Local PostgreSQL only
```

Cloud remains coordination/public-intake only. It must never become authoritative for invoices, payments, ledger, stock movements, purchase receiving, daily closing, or audit history.

## 4. Next milestone: prepare the physical Local Hub

This is the next task when work resumes.

Recommended AI-capable hardware baseline:

```text
CPU: Intel Core i5 10th Gen or newer / equivalent Ryzen 5
RAM: 16 GB works for operations/OCR/API-based AI
RAM: 32 GB recommended for local LLMs + OCR + PostgreSQL
Storage: 512 GB NVMe minimum; 1 TB preferred
Network: Gigabit Ethernet
Power: UPS for Hub + router/ONT
Backup: separate external target
```

Primary deployment guide:

```text
docs/LOCAL_HUB_LINUX_DEPLOYMENT.md
```

Primary go-live checklist:

```text
docs/PRODUCTION_GO_LIVE_CHECKLIST.md
```

## 5. Local Hub installation sequence

### Step 1 — Install operating-system dependencies

On the final Omarchy/Arch or Linux Hub install:

- PostgreSQL server/client;
- Python + virtualenv/build dependencies;
- Node.js/npm;
- Git;
- curl;
- any printer/tunnel packages required by the physical deployment.

Use Linux system services; daily operation must not depend on an interactive terminal or graphical login.

### Step 2 — Install application under production paths

Expected layout:

```text
/opt/kalpvrik                       application checkout/build
/etc/kalpvrik/local-hub.env        protected runtime secrets
/var/lib/kalpvrik                   runtime/backups
/var/log/kalpvrik                   optional application logs
```

Create the `kalpvrik` service account and follow the exact commands in `docs/LOCAL_HUB_LINUX_DEPLOYMENT.md`.

### Step 3 — Install backend dependencies

```bash
cd /opt/kalpvrik/backend
python -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

### Step 4 — Create protected Local Hub configuration

Create:

```text
/etc/kalpvrik/local-hub.env
```

Minimum shape:

```text
ENVIRONMENT=production
DEPLOYMENT_MODE=local_hub
DATABASE_URL=postgresql+psycopg://...
LOCAL_DATABASE_URL=postgresql+psycopg://...
LOCAL_BACKUP_DATABASE_URL=postgresql://...
SECRET_KEY=<strong unique production secret>
FRONTEND_ORIGIN=https://<hosted-frontend>
FRONTEND_EXTRA_ORIGINS=http://<local-ui-origin>,https://<approved-extra-origin>
CLOUD_GATEWAY_BASE_URL=https://<cloud-gateway-host>
SYNC_DEVICE_SECRET=<strong unique device secret>
SYNC_DEVICE_NAME=Local Business Hub
KALPVRIK_BACKUP_ROOT=/var/lib/kalpvrik/backups/postgres
KALPVRIK_PUBLICATION_STATE=/var/lib/kalpvrik/menu-publication-state.json
```

Never commit this environment file or any production secret.

### Step 5 — Prepare Local PostgreSQL

PostgreSQL is the final operational/financial authority.

Security rule:

```text
TCP 5432 must never be publicly exposed.
```

Run local migrations:

```bash
cd /opt/kalpvrik/backend
set -a; source /etc/kalpvrik/local-hub.env; set +a
.venv/bin/alembic -c alembic.ini upgrade head
.venv/bin/alembic -c alembic.ini current
```

Expected Local Hub migration head:

```text
20260821_0019
```

### Step 6 — Build the local staff/POS frontend

The local frontend must keep POS/waiter/kitchen operational when internet is unavailable.

```bash
cd /opt/kalpvrik/frontend
npm ci
VITE_OPERATIONAL_API_BASE_URL=http://kalpvrik-hub.local:8000/api \
VITE_API_BASE_URL=http://kalpvrik-hub.local:8000/api \
VITE_CLOUD_API_BASE_URL=https://<cloud-gateway-host>/api \
npm run build
```

No secret belongs in any `VITE_*` variable.

### Step 7 — Enable Local Hub systemd services

```bash
sudo systemctl enable --now kalpvrik-api.service
sudo systemctl enable --now kalpvrik-sync.service
sudo systemctl enable --now kalpvrik-frontend.service
sudo systemctl enable --now kalpvrik-backup.timer
sudo systemctl enable --now kalpvrik-menu-publish.timer
```

Verify:

```bash
sudo -u kalpvrik bash /opt/kalpvrik/scripts/check_local_hub.sh
systemctl list-timers 'kalpvrik-*'
```

Expected boot model:

```text
Power on
  -> PostgreSQL
  -> Local FastAPI
  -> sync worker
  -> local frontend/PWA
  -> backup timer
  -> menu publication timer
  -> tunnel/private access service
```

## 6. Cloud production setup after Local Hub base is ready

### Step 1 — Supabase production coordination DB

Create/use the final production Supabase project.

Store only cloud coordination/public-safe data.

Apply cloud migrations:

```bash
alembic -c alembic_cloud.ini upgrade head
```

Expected cloud head:

```text
20260821_cloud_0003
```

### Step 2 — Configure the Vercel Cloud Gateway

Required concepts:

```text
ENVIRONMENT=production
DEPLOYMENT_MODE=cloud_gateway
SECRET_KEY=<strong unique secret>
CLOUD_RUNTIME_DATABASE_URL=<Supabase runtime/pooler URL>
CLOUD_MIGRATION_DATABASE_URL=<protected Supabase migration/direct URL>
FRONTEND_ORIGIN=https://<production-frontend>
FRONTEND_EXTRA_ORIGINS=<explicit approved origins only>
```

Then verify:

```text
GET /api/cloud/readiness
```

Expected:

```text
status = ready
cloud_schema_revision = 20260821_cloud_0003
```

Cloud mode must not expose local-only billing/inventory/admin write routes.

### Step 3 — Configure hosted frontend environment

```text
VITE_CLOUD_API_BASE_URL=https://<cloud-gateway>/api
VITE_OPERATIONAL_API_BASE_URL=https://<approved-local-hub-tunnel>/api
```

Never place service-role keys, DB URLs, `SECRET_KEY`, or `SYNC_DEVICE_SECRET` in browser variables.

## 7. Join Local Hub to cloud

After the cloud migration is complete:

### Register Local Hub device

```bash
cd /opt/kalpvrik/backend
set -a; source /etc/kalpvrik/local-hub.env; set +a
export CLOUD_MIGRATION_DATABASE_URL='postgresql+psycopg://<protected-direct-supabase-url>'
.venv/bin/python -m scripts.register_cloud_device
```

The cloud should store only the device-secret hash, never the raw secret.

### Publish the first customer-safe Cafe snapshot

```bash
.venv/bin/python -m scripts.publish_cafe_menu --force
```

Confirm that only customer-safe menu/table/QR/availability data is published.

## 8. Configure remote Super Admin access

Expose FastAPI, never PostgreSQL.

Recommended model:

```text
Remote owner
  -> HTTPS
  -> Cloudflare Tunnel or private Tailscale path
  -> Local Hub FastAPI
  -> Local PostgreSQL
```

Keep TCP 5432 private.

## 9. Enroll privileged MFA

Before public remote administration:

- enroll final Super Admin in TOTP;
- enroll every publicly reachable Venture Admin;
- store recovery codes offline;
- confirm password-only privileged production login is rejected;
- confirm valid TOTP succeeds;
- confirm invalid TOTP fails;
- confirm recovery code works only once.

See:

```text
docs/MFA_PRODUCTION_SETUP.md
```

## 10. Physical go-live tests

Do not mark production ready until the following are tested on the real hardware/network.

### Multi-device

- POS login/billing/printing;
- waiter workflow;
- kitchen preparation view;
- manager/owner scope;
- two users on one table;
- two simultaneous bill attempts;
- last-stock concurrency.

### Customer QR

- physical QR scan from a normal phone using mobile data;
- menu loads through hosted/cloud path;
- browser price manipulation cannot alter authoritative pricing;
- duplicate submission creates one cloud order;
- cloud order survives Hub outage and imports after recovery;
- Request Bill creates one durable request and no cloud financial transaction;
- invalid/revoked QR fails safely.

### Remote Super Admin

- HTTPS access from outside the cafe network;
- live data comes from Local Hub;
- financial/stock writes never silently fall back to cloud when Hub is unavailable.

### Failure/recovery

- disconnect internet while keeping LAN alive: POS/waiter/kitchen/local billing continue;
- reconnect internet: queues drain automatically;
- stop/reboot Hub: services and timers recover without manual login;
- duplicate delivery creates no duplicate financial/stock effect;
- test UPS shutdown/recovery.

### Backup/restore

- scheduled `pg_dump` completes;
- SHA-256 sidecar verifies;
- copy backup to storage independent of Hub SSD;
- restore into a disposable PostgreSQL database;
- verify migration head, users, invoices, inventory, sync queues/checkpoints.

## 11. Exact restart point for the next session

When the Local Hub hardware is physically available, restart work here:

```text
1. Confirm the Hub OS and hardware specs.
2. Clone/pull current main.
3. Install PostgreSQL/Python/Node/system packages.
4. Create the kalpvrik service account and production directories.
5. Create Local PostgreSQL database/user.
6. Create /etc/kalpvrik/local-hub.env.
7. Run local migration -> 20260821_0019.
8. Build local frontend.
9. Install/enable systemd services and timers.
10. Run check_local_hub.sh.
11. Then configure Supabase production/cloud migration.
12. Re-check Vercel production API status.
13. Register the Local Hub device.
14. Publish the first Cafe snapshot.
15. Configure the secure remote tunnel.
16. Enroll MFA.
17. Run the complete physical go-live checklist.
```

Do not start OCR/purchase-bill ingestion, local LLM/chatbot expansion, or other new features until this deployment sequence is complete.

## 12. Status summary at pause

```text
ARCHITECTURE / PRODUCT CODE          DONE
RELEASE PR -> MAIN                   DONE
REPOSITORY RELEASE GATES             DONE
FRONTEND PRODUCTION DEPLOYMENT       GREEN
API RELEASE CODE / PREVIEW           VERIFIED
API MAIN PRODUCTION DEPLOYMENT       BLOCKED BY VERCEL FREE-TIER QUOTA

LOCAL HUB HARDWARE                   NEXT
LOCAL HUB OS / SERVICES              NOT YET INSTALLED ON FINAL MACHINE
LOCAL POSTGRESQL PROD DB             NOT YET CONFIGURED
SUPABASE PROD COORDINATION DB        NOT YET FINALIZED
CLOUD PROD MIGRATION                 NOT YET APPLIED
LOCAL DEVICE REGISTRATION            NOT YET DONE
FIRST CAFE CLOUD PUBLICATION         NOT YET DONE
REMOTE HTTPS TUNNEL                  NOT YET DONE
PRODUCTION MFA ENROLLMENT            NOT YET DONE
PHYSICAL MULTI-DEVICE TEST           NOT YET DONE
OUTAGE / REBOOT TEST                 NOT YET DONE
REAL INDEPENDENT BACKUP / RESTORE    NOT YET DONE
PUBLIC GO-LIVE                       NOT YET APPROVED
```

This is an intentional pause, not an unfinished architecture phase. Resume with Local Hub installation and production-environment evidence, not with a new development phase.
