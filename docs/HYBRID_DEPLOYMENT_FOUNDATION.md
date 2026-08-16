# Hybrid Deployment Foundation

## Status

- Phase: HC0
- Status: Runtime and migration boundaries implemented; Supabase behavior and synchronization not implemented
- Last updated: 2026-08-11

## Purpose

This guide defines how the same repository is prepared for two fail-closed runtime profiles without confusing their databases or credentials.

## Deployment Profiles

| Profile | Entry point | Database | Allowed HC0 routes |
| --- | --- | --- | --- |
| Local Business Hub | `uvicorn app.main:app` | Local PostgreSQL | Health plus all existing operational APIs |
| Vercel cloud gateway | `backend/server.py` | Supabase runtime connection | Health only until later HC phases add approved cloud APIs |

`backend/server.py` refuses to start unless `DEPLOYMENT_MODE=cloud_gateway`. Cloud mode does not register inventory adjustment, invoice issue, payment, ledger, purchase, purge, backup, AI, or unrestricted reporting routes.

## Database And Migration Boundaries

Local runtime and existing migration history:

```powershell
cd backend
alembic -c alembic.ini upgrade head
```

This command uses `LOCAL_DATABASE_URL`, falling back to the legacy `DATABASE_URL`. It preserves the existing `alembic_version` table.

Cloud coordination migration history:

```powershell
cd backend
alembic -c alembic_cloud.ini upgrade head
```

This command requires `CLOUD_MIGRATION_DATABASE_URL` and uses a separate `alembic_version_cloud` table. HC0 contains no cloud business migration yet.

The configuration rejects cloud runtime or migration URLs that identify the same host, port, and database as the Local Hub URL. Always rehearse local and cloud migrations against separate disposable databases before production.

## Supabase Connections

Use two server-side Supabase connection settings:

- `CLOUD_RUNTIME_DATABASE_URL`: Supabase transaction pooler for Vercel runtime traffic.
- `CLOUD_MIGRATION_DATABASE_URL`: supported direct or session connection for Alembic and administrative work.

Use the SQLAlchemy `postgresql+psycopg://` driver form. Require TLS with the connection parameters supplied by Supabase. Never put either URL in a `VITE_*` variable.

No Supabase tables, policies, grants, or synchronization writes are created in HC0.

## Vercel Project Layout

Recommended project roots:

1. Frontend project root: `frontend`.
2. Cloud gateway project root: `backend`.

For the backend project:

- Vercel detects `server.py` as the FastAPI entry point.
- Set `DEPLOYMENT_MODE=cloud_gateway`.
- Configure values from `backend/.env.cloud.example` in Vercel project settings.
- Do not upload `.env` files.
- Keep API documentation disabled in production.

For the frontend project:

- Build command: `npm run build`.
- Output directory: `dist`.
- Only `VITE_*` values are public browser configuration.
- HC2 will implement the final cloud/operational API routing and rewrites.

## Local Business Hub Installation Design

At least one owner-controlled device runs the Local Hub. A native desktop shell is not required. Staff use the locally served React PWA or browser shortcut.

Required managed processes:

1. PostgreSQL service.
2. FastAPI Local Hub service.
3. Static React/PWA server or reverse proxy.
4. Synchronization worker, added in HC1.
5. Backup and backup-age monitoring jobs.

Required startup order:

1. Start PostgreSQL.
2. Wait for database health.
3. Start FastAPI and verify `/api/health` reports `local_hub`.
4. Start the local frontend.
5. Start the synchronization worker after HC1.
6. Mark the installation operational only after required health checks pass.

On Windows, install the API, frontend server, and future worker through an approved service manager or packaged installer with automatic startup and restart-on-failure. On Linux, use equivalent system services. Implementation scripts are intentionally deferred until HC1 has a real worker command to supervise.

The Local Hub device should use a reserved LAN address or hostname, restricted firewall rules, scheduled backups, and preferably a UPS. PostgreSQL must not be exposed by the tunnel.

## Credential Classification

| Credential or setting | Location | Browser-visible | Rotation owner |
| --- | --- | --- | --- |
| `VITE_API_BASE_URL` and future public API URLs | Vercel/frontend environment | Yes | Deployment admin |
| Local PostgreSQL password | Local Hub server environment | No | Final Super Admin/operator |
| Local `SECRET_KEY` | Local Hub server environment | No | Final Super Admin/operator |
| Supabase runtime database URL | Vercel backend environment | No | Cloud deployment admin |
| Supabase migration database URL | Admin/CI migration environment | No | Database migration admin |
| Supabase secret/service-role key, if later required | Vercel backend only | No | Cloud deployment admin |
| Device credential, added in HC1 | Local protected store and cloud registration | No | Final Super Admin/operator |
| OpenAI key | Backend environment only | No | Final Super Admin/operator |

Rules:

- Never commit real `.env` files or credentials.
- Never prefix a secret with `VITE_`.
- Use separate runtime, migration, and device credentials.
- Give runtime roles only the permissions required by registered cloud routes.
- Rotate credentials through documented procedures without deleting queue state.
- Redact passwords and keys from logs, error responses, screenshots, and phase reports.

## Local Run

```powershell
Copy-Item ..\.env.example .env
$env:DEPLOYMENT_MODE="local_hub"
uvicorn app.main:app --reload
```

Expected health response includes:

```json
{
  "status": "healthy",
  "deployment_mode": "local_hub",
  "database_configured": true
}
```

## Cloud Gateway Local Check

Use disposable cloud configuration only:

```powershell
$env:DEPLOYMENT_MODE="cloud_gateway"
$env:CLOUD_RUNTIME_DATABASE_URL="postgresql+psycopg://..."
$env:CLOUD_MIGRATION_DATABASE_URL="postgresql+psycopg://..."
uvicorn server:app --reload
```

At HC0, `/api/health` is available and operational business routes return `404`.

## HC0 Safety Checklist

- Local mode exposes current operational routes.
- Cloud mode exposes health only.
- Production API docs are disabled.
- Existing local Alembic history is unchanged.
- Cloud Alembic history is independent.
- Runtime and migration URLs cannot identify the Local Hub database.
- Frontend templates contain no secret key.
- No Supabase schema or synchronization behavior has been implemented early.

