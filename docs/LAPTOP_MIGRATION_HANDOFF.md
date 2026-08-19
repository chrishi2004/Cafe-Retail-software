# Cafe-Retail Software: Laptop Migration Handoff

This document is the non-secret handoff for continuing the project on another
Windows laptop. It intentionally does not contain passwords, API keys, tunnel
tokens, `.env` files, PostgreSQL data, or virtual environments.

## Repository and release state

- GitHub repository: `https://github.com/chrishi2004/Cafe-Retail-software`
- Default branch: `main`
- Latest verified main commit at the time of this handoff: `c2412290be801d1cd7c7704606fc6edb291d2158`
- Do not copy the local `.venv`, PostgreSQL data directory, backups, or secret files.

The merged release includes the P1-P11 implementation and the R1-R4 hybrid
cloud continuity work. The next work must begin by checking the current
`main` branch and reading the source-of-truth documents listed in the root
`README.md`.

## Approved operating model

The system has two deliberate deployment profiles:

1. **Local Business Hub** on the owner laptop: authentication, Retail, Cafe,
   billing, dashboards, exports, AI, governance, and the operational PostgreSQL
   database.
2. **Vercel cloud gateway**: restricted continuity and customer-safe cloud
   routes only, backed by the Supabase coordination schema.

PostgreSQL port `5432` must remain private. Remote access to the Local Hub
must use HTTPS through a protected tunnel or private network service.

## Current hosted services

- Frontend: `https://cafe-retail-software.vercel.app`
- Cloud gateway: `https://cafe-retail-api.vercel.app`
- Cloud gateway health: `https://cafe-retail-api.vercel.app/api/health`
- Cloud gateway readiness: `https://cafe-retail-api.vercel.app/api/cloud/readiness`
- GitHub Actions: `https://github.com/chrishi2004/Cafe-Retail-software/actions`

The cloud gateway readiness endpoint must report `status=ready` and
`database_ready=true` before cloud continuity work is considered operational.

## Supabase coordination project

- Project ref: `eplnxbfxilkhwlbtlghn`
- Project URL: `https://eplnxbfxilkhwlbtlghn.supabase.co`
- Cloud schema revision applied: `20260814_cloud_0002`
- Supabase is the coordination database for the cloud gateway, not the local
  operational system of record.

Use the Supabase dashboard to retrieve or reset database credentials. Never
commit those credentials or paste them into GitHub, issues, or this document.

## Vercel environment names

### Backend project: `cafe-retail-api`

Required Production variables include:

```text
DEPLOYMENT_MODE=cloud_gateway
CLOUD_RUNTIME_DATABASE_URL=<Supabase transaction-pooler URL with URL-encoded password and sslmode=require>
CLOUD_MIGRATION_DATABASE_URL=<Supabase migration URL with URL-encoded password and sslmode=require>
CLOUD_GATEWAY_BASE_URL=https://cafe-retail-api.vercel.app/api
FRONTEND_ORIGIN=https://cafe-retail-software.vercel.app
SECRET_KEY=<long random production value>
```

Optional continuity variables are documented in
`docs/CLOUD_DEPLOYMENT_RUNBOOK.md` and `docs/LOCAL_HUB_DEVICE_SETUP.md`.

### Frontend project: `cafe-retail-software`

```text
VITE_CLOUD_API_BASE_URL=https://cafe-retail-api.vercel.app/api
VITE_OPERATIONAL_API_BASE_URL=<stable HTTPS Local Hub URL>/api
VITE_API_BASE_URL=<stable HTTPS Local Hub URL>/api
```

Never put database passwords, service-role keys, device secrets, or other
server-only values in a `VITE_*` variable.

## First-time setup on a new Windows laptop

Install Git, Python, Node.js, PostgreSQL, and `cloudflared`. Then:

```powershell
git clone https://github.com/chrishi2004/Cafe-Retail-software.git
cd Cafe-Retail-software

python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Create `backend/.env` from the repository examples. Keep it local and set a
new strong `SECRET_KEY`, the local PostgreSQL URL, and:

```text
DEPLOYMENT_MODE=local_hub
FRONTEND_ORIGIN=https://cafe-retail-software.vercel.app
```

Apply the local schema and seed development data only when a disposable demo
database is intended:

```powershell
cd backend
.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
.venv\Scripts\python.exe scripts\seed_multi_venture.py --reset
cd ..
```

Start and verify the Local Hub:

```powershell
.\scripts\start_local_hub.ps1
```

In another terminal:

```powershell
.\scripts\check_local_hub.ps1
```

The local health URL is `http://127.0.0.1:8000/api/health`.

## Stable remote access status

A Cloudflare named tunnel named `cafe-retail-hub` was created in the
Cloudflare account, but its connector installation and public hostname still
require completion. The tunnel credentials are intentionally not stored here.

The permanent setup requires:

1. Add a domain controlled by the owner to Cloudflare.
2. Run the Windows connector command shown inside the Cloudflare tunnel page
   as Administrator.
3. Publish a hostname such as `api.example-domain.online` to
   `http://127.0.0.1:8000`.
4. Verify `https://api.example-domain.online/api/health`.
5. Set both frontend operational API variables to that stable HTTPS URL and
   redeploy the frontend.

Quick `trycloudflare.com` URLs are temporary and must not be recorded as
production configuration.

## Source-of-truth documents

Read these before changing architecture or starting a new phase:

- `README.md`
- `PRD_MULTI_VENTURE_CAFE_EXPANSION.md`
- `TRD_MULTI_VENTURE_CAFE_EXPANSION.md`
- `PRD_HYBRID_CLOUD_CONTINUITY_ADDENDUM.md`
- `TRD_HYBRID_CLOUD_CONTINUITY.md`
- `docs/MULTI_VENTURE_CAFE_IMPLEMENTATION_PHASES.md`
- `docs/HYBRID_CLOUD_CONTINUITY_IMPLEMENTATION_PHASES.md`
- `docs/CLOUD_DEPLOYMENT_RUNBOOK.md`
- `docs/LOCAL_HUB_DEVICE_SETUP.md`
- `docs/FINAL_PRODUCT_OPERATING_MODEL.md`

## Secret and data handling

Never commit:

- `backend/.env` or any real `.env` file
- Supabase or PostgreSQL passwords
- Vercel `SECRET_KEY`
- `SYNC_DEVICE_SECRET`
- Cloudflare tunnel tokens or credentials JSON
- Supabase service-role keys
- `.venv` directories
- PostgreSQL data folders, exports, backups, or local logs containing tokens

Before switching laptops, back up business data separately with an encrypted
PostgreSQL backup and transfer secrets through a password manager or the
platform dashboards. Do not put either into Git.
