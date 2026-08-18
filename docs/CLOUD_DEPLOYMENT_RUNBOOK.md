# Cloud Deployment Runbook

This project has a deliberate three-part deployment model:

1. **Local Hub** — the business's FastAPI operational API and PostgreSQL system of record.
2. **Vercel frontend** — customer QR ordering plus the authenticated staff/owner interface.
3. **Vercel cloud gateway** — a restricted FastAPI service backed by Supabase coordination storage.

The cloud gateway is not the replacement for the Local Hub. It handles safe public continuity,
menu publication, signed device synchronization, and cloud coordination. Billing, inventory,
invoices, and other financial writes remain Local Hub-authoritative.

## 1. Create the free-tier external services

- Create a Supabase project for this repository's cloud coordination database.
- Create two Vercel projects from the same GitHub repository:
  - the frontend project, rooted at `frontend`;
  - the backend gateway project, rooted at `backend` and using the restricted `server:app` entrypoint.
- Keep the Local Hub PostgreSQL instance on the operator device for the first release. A secure
  tunnel or private network path is required before a hosted frontend can call it.

Do not commit credentials, `.env` files, Supabase service-role keys, or device secrets.

## 2. Prepare Supabase coordination storage

From the `backend` directory, use the Supabase transaction-pooler URL for runtime and the direct
database URL for migrations. Set the migration variable only in a protected local shell or CI
secret store, then run:

```powershell
$env:CLOUD_MIGRATION_DATABASE_URL="postgresql+psycopg://..."
alembic -c alembic_cloud.ini upgrade head
```

The cloud Alembic chain is independent from the Local Hub chain. Never point either cloud URL at
the Local Hub database. The cloud migration URL is required even when the runtime pooler URL is
already configured.

## 3. Configure the Vercel backend gateway

Set these variables in the backend Vercel project's Production environment:

```text
DEPLOYMENT_MODE=cloud_gateway
CLOUD_RUNTIME_DATABASE_URL=<Supabase transaction-pooler URL>
CLOUD_MIGRATION_DATABASE_URL=<protected migration URL, if migrations run in this environment>
SECRET_KEY=<long random production value>
FRONTEND_ORIGIN=<frontend production origin>
FRONTEND_EXTRA_ORIGINS=<additional approved origins, if needed>
```

The gateway must use `server:app`; do not deploy `app.main:app` as the cloud gateway because that
would expose Local Hub operational routes. The gateway's health endpoint is:

```text
https://<gateway-host>/api/health
```

The safe readiness endpoint is:

```text
https://<gateway-host>/api/cloud/readiness
```

It returns only booleans and version/status data. It never returns database URLs, passwords, or
device credentials. `status=ready` means the database is reachable and both required cloud URL
settings are present. Recommended device/gateway checks are shown separately for continuity setup.

## 4. Configure the Local Hub

Copy the root `.env.example` to a private `.env` and keep `DEPLOYMENT_MODE=local_hub`. Configure:

```text
DATABASE_URL=<Local Hub PostgreSQL URL>
LOCAL_DATABASE_URL=<same Local Hub URL>
CLOUD_GATEWAY_BASE_URL=https://<gateway-host>/api
SYNC_DEVICE_ID=<registered device id>
SYNC_DEVICE_SECRET=<server-side device secret>
SYNC_BUSINESS_GROUP_ID=<authorized scope>
SYNC_COMPANY_ID=<authorized scope>
SYNC_BRANCH_ID=<authorized scope>
```

`SYNC_DEVICE_SECRET` is server-side only. Never add it to a `VITE_*` variable, browser bundle,
GitHub issue, screenshot, or Vercel frontend project.

## 5. Configure the Vercel frontend

Set these variables in the frontend Vercel project's Production environment:

```text
VITE_OPERATIONAL_API_BASE_URL=<secure Local Hub/tunnel URL>/api
VITE_API_BASE_URL=<secure Local Hub/tunnel URL>/api
VITE_CLOUD_API_BASE_URL=https://<gateway-host>/api
```

The operational URL must be HTTPS and must not be an unauthenticated public database/API exposure.
For a first device-only release, the Local Hub can remain private and the customer QR flow can use
the cloud continuity path. Staff and owner portals need a reachable operational API to sign in.

## 6. Verify in order

1. Confirm Local Hub health and authenticated login locally.
2. Confirm Supabase cloud migrations are at the current cloud head.
3. Confirm gateway `/api/health`.
4. Confirm gateway `/api/cloud/readiness` reports `ready`.
5. Register the Local Hub device through the approved HC1/HC2 flow and verify the recommended
   readiness checks become true.
6. Publish a safe cafe menu and resolve one opaque QR token.
7. Place a continuity-mode customer order and verify status refresh.
8. Verify that billing, inventory, invoice, and staff operations still route to the Local Hub.
9. Run the repository P1–P11 GitHub Actions gates before release.

Cloud-only integration checks require protected environment variables such as
`HC2_TEST_CLOUD_DATABASE_URL`, `HC3_TEST_CLOUD_DATABASE_URL`, and
`HC4_TEST_CLOUD_DATABASE_URL`. Missing values should remain explicit skips, not fake credentials.

## Current release boundary and next step

The system is ready for configuration validation, but a production release still needs the actual
Supabase project URLs, Vercel environment variables, device registration, and a secure path from
the hosted frontend to the Local Hub for internal portals. The next implementation phase should
automate or improve those operator-facing setup checks; it must not move financial authority into
the cloud gateway.
