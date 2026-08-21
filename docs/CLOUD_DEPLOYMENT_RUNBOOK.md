# Cloud Deployment Runbook

This project uses a deliberate three-part deployment model:

1. **Local Hub** — full FastAPI operational API plus the authoritative PostgreSQL business database.
2. **Hosted frontend** — customer QR ordering plus authenticated staff/owner UI.
3. **Restricted Cloud Gateway** — limited FastAPI service backed by the Supabase coordination database.

The Cloud Gateway is not a replacement for the Local Hub. Billing, inventory, invoices, payments, ledgers, stock movements, purge/governance and unrestricted operational data remain Local-Hub authoritative.

## 1. External services

Create:

- one Supabase project for cloud coordination storage;
- one Vercel frontend project rooted at `frontend`;
- one Vercel backend project rooted at `backend`.

The backend Vercel project must run the restricted `server:app` entrypoint. Never deploy `app.main:app` or `operational_server:app` as the public cloud gateway.

Do not commit credentials, `.env` files, Supabase database passwords, device secrets or service-role keys.

## 2. Apply cloud coordination migrations

Use the Supabase transaction-pooler URL for `CLOUD_RUNTIME_DATABASE_URL` and the protected direct/migration URL for `CLOUD_MIGRATION_DATABASE_URL`.

From `backend`:

```bash
export CLOUD_MIGRATION_DATABASE_URL='postgresql+psycopg://...'
alembic -c alembic_cloud.ini upgrade head
alembic -c alembic_cloud.ini current
```

Expected cloud head for this release:

```text
20260821_cloud_0003
```

The cloud Alembic chain is independent from the Local Hub chain. Never point a cloud URL at the Local Hub database.

## 3. Configure the Vercel Cloud Gateway

Production variables:

```text
DEPLOYMENT_MODE=cloud_gateway
CLOUD_RUNTIME_DATABASE_URL=<Supabase transaction-pooler URL>
CLOUD_MIGRATION_DATABASE_URL=<protected migration URL if needed by the runtime/readiness policy>
SECRET_KEY=<strong unique production secret>
ENVIRONMENT=production
FRONTEND_ORIGIN=https://<hosted-frontend>
FRONTEND_EXTRA_ORIGINS=<comma-separated approved extra origins, if any>
```

Health:

```text
https://<gateway-host>/api/health
```

Readiness:

```text
https://<gateway-host>/api/cloud/readiness
```

The readiness response must report `cloud_schema_revision=20260821_cloud_0003` before go-live.

## 4. Configure the Local Hub

Create the private Local Hub environment file from `.env.example` and set at minimum:

```text
ENVIRONMENT=production
DEPLOYMENT_MODE=local_hub
DATABASE_URL=<Local Hub PostgreSQL SQLAlchemy URL>
LOCAL_DATABASE_URL=<same Local Hub URL>
LOCAL_BACKUP_DATABASE_URL=<pg_dump-compatible PostgreSQL URL>
SECRET_KEY=<strong unique Local Hub production secret>
FRONTEND_ORIGIN=https://<hosted-frontend>
FRONTEND_EXTRA_ORIGINS=http://<local-ui-origin>,https://<other-explicit-approved-origin>
CLOUD_GATEWAY_BASE_URL=https://<gateway-host>
SYNC_DEVICE_SECRET=<strong random device secret>
SYNC_DEVICE_NAME=Local Business Hub
```

`CLOUD_GATEWAY_BASE_URL` may be supplied as either `https://<gateway-host>` or `https://<gateway-host>/api`. The transport normalizes both forms and never duplicates `/api`. The host-root form is preferred for new installations.

`SYNC_DEVICE_SECRET` is server-side only. Never place it in `VITE_*`, frontend source, logs, screenshots, issues or chat.

Apply the Local Hub migration:

```bash
cd /opt/kalpvrik/backend
set -a; source /etc/kalpvrik/local-hub.env; set +a
.venv/bin/alembic -c alembic.ini upgrade head
.venv/bin/alembic -c alembic.ini current
```

Expected Local Hub head:

```text
20260821_0019
```

## 5. Register the Local Hub device

Registration is a trusted operator action because it writes the device credential **hash** and scope to the cloud coordination database. The raw secret remains only on the Local Hub.

Temporarily provide the protected cloud migration URL in the trusted shell/environment and run from `backend`:

```bash
python -m scripts.register_cloud_device
```

When the Local Hub contains exactly one active business group, the script discovers it automatically and registers the device at business-group scope. To restrict a device further:

```bash
python -m scripts.register_cloud_device --business-group-id 1 --company-id 2 --branch-id 3
```

If intentionally rotating `SYNC_DEVICE_SECRET` for an already registered device:

```bash
python -m scripts.register_cloud_device --rotate-secret
```

The command refuses accidental secret replacement. It never prints the raw secret and never stores the raw secret in the cloud database.

Default device purposes are:

```text
heartbeat
menu_publication
sync_pull
sync_push
```

After registration, remove the direct cloud migration URL from any transient shell where it is no longer needed. Keep protected server-side configuration according to the chosen deployment procedure.

## 6. Publish the first Cafe menu snapshot

The customer QR route is cloud-primary, so the Cloud Gateway must have a current sanitized menu/QR publication.

From the Local Hub `backend` directory:

```bash
python -m scripts.publish_cafe_menu --force
```

The publisher:

- reads Cafe categories/items/tables/active QR references from Local PostgreSQL;
- publishes only the approved customer-safe snapshot;
- sends no cost price, password hash, ledger, payment or unrestricted customer data;
- authenticates with the registered Local Hub device;
- records a non-secret local fingerprint so unchanged menus are not republished repeatedly.

Production Linux installs also use `kalpvrik-menu-publish.timer`, which checks every two minutes and publishes only when the customer-safe snapshot changes.

## 7. Configure the hosted frontend

Frontend Vercel production variables:

```text
VITE_CLOUD_API_BASE_URL=https://<gateway-host>/api
VITE_OPERATIONAL_API_BASE_URL=https://<secure-local-hub-tunnel>/api
VITE_API_BASE_URL=https://<secure-local-hub-tunnel>/api
```

The hosted `/order/:qr-token` route uses the Cloud Gateway. Staff/owner portals use the Operational Local Hub.

No service-role key, database password, device secret or backend credential may exist in a `VITE_*` variable.

## 8. Remote operational access

Expose only FastAPI through the approved authenticated HTTPS tunnel/private network. Never expose PostgreSQL TCP 5432.

Recommended boundary:

```text
Hosted frontend -> HTTPS tunnel/private network -> Local Hub FastAPI
Local Hub FastAPI -> Local PostgreSQL
Customer QR -> Hosted frontend -> Cloud Gateway -> Supabase coordination
Cloud Gateway <-> Local Hub durable sync
```

## 9. Verify in order

1. Local Hub migration is `20260821_0019`.
2. Cloud migration is `20260821_cloud_0003`.
3. Local API health passes.
4. Cloud `/api/health` passes.
5. Cloud `/api/cloud/readiness` reports `ready`.
6. Device registration command succeeds.
7. Sync worker heartbeat and writer lease become healthy.
8. `python -m scripts.publish_cafe_menu --force` succeeds.
9. A physical QR resolves through the hosted/cloud path.
10. Customer order is durable in cloud and imports once locally.
11. Customer bill request produces only a local `bill_requested` state until staff billing.
12. POS/waiter/kitchen continue locally during internet loss.
13. Remote Super Admin works only through the approved operational endpoint.
14. Backup/restore and physical outage tests in `docs/PRODUCTION_GO_LIVE_CHECKLIST.md` are evidenced.
15. `Release Readiness` is green for the exact commit or PR being released.

## Release boundary

Repository implementation is considered deployment-shaped only when the final release branch/PR passes `Release Readiness`. Public-production readiness still requires actual Supabase/Vercel environment values, the real Local Hub, device registration, menu publication, secure tunnel/network configuration, privileged MFA enrollment and physical failure/recovery evidence.

Do not move financial authority into the Cloud Gateway to work around an unavailable Local Hub. Customer ordering may remain cloud-primary while invoices/payments/stock/ledger authority remains local.
