# HC0 Phase Report: Runtime, Configuration, And Migration Boundaries

## Status

- Phase: HC0
- Status: Complete
- Date: 2026-08-11

## Files Changed

- `backend/app/core/config.py`
- `backend/app/db/session.py`
- `backend/app/main.py`
- `backend/app/api/routes/health.py`
- `backend/alembic/env.py`
- `backend/alembic_cloud.ini`
- `backend/alembic_cloud/`
- `backend/app/cloud_db/`
- `backend/server.py`
- `backend/.env.cloud.example`
- `.env.example`
- `frontend/.env.example`
- `backend/tests/test_deployment_modes.py`
- `backend/README.md`
- `docs/HYBRID_DEPLOYMENT_FOUNDATION.md`
- `README.md`
- `PRD_MULTI_VENTURE_CAFE_EXPANSION.md`
- `TRD_MULTI_VENTURE_CAFE_EXPANSION.md`
- `AGENT_STEP_BY_STEP_PROMPTS_MULTI_VENTURE_CAFE.md`
- `docs/MULTI_VENTURE_CAFE_IMPLEMENTATION_PHASES.md`
- `PRD_HYBRID_CLOUD_CONTINUITY_ADDENDUM.md`
- `TRD_HYBRID_CLOUD_CONTINUITY.md`
- `docs/HYBRID_CLOUD_CONTINUITY_IMPLEMENTATION_PHASES.md`

## Requirements Completed

- Added `local_hub` and `cloud_gateway` deployment modes.
- Kept legacy `DATABASE_URL` compatibility for existing local setups.
- Added explicit local runtime, cloud runtime, and cloud migration database settings.
- Added fail-closed cloud route registration. HC0 cloud mode exposes health only.
- Added production API documentation disabling by default.
- Added a Vercel FastAPI entry point at `backend/server.py`.
- Preserved the existing local Alembic history and version table.
- Added an independent cloud Alembic environment and version table boundary.
- Added database-target collision validation.
- Added local and cloud environment templates without secrets.
- Added Local Hub installation, service startup, credential, Vercel, and migration documentation.
- Added tests for route isolation, mode configuration, database target separation, API-doc lockdown, and migration separation.
- Updated the hybrid PRD, TRD, phase plan, prompt book, README, and architecture references.

## Commands Run

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q --disable-warnings tests/test_deployment_modes.py tests/test_auth.py tests/test_master_data.py tests/test_inventory.py tests/test_sales.py
.\.venv\Scripts\python.exe -m pytest -q --disable-warnings tests/test_business_settings.py tests/test_customers.py tests/test_customer_ledger.py tests/test_products_retail_catalog.py tests/test_invoices.py tests/test_invoice_tax.py tests/test_pos_checkout.py tests/test_purchase_orders.py
.\.venv\Scripts\python.exe -m pytest -q --disable-warnings tests/test_ai.py tests/test_dashboard.py tests/test_exports.py tests/test_forecasts.py tests/test_reorder.py tests/test_business_workflows.py
.\.venv\Scripts\python.exe -m compileall -q app server.py
.\.venv\Scripts\alembic.exe -c alembic.ini heads
.\.venv\Scripts\alembic.exe -c alembic_cloud.ini heads

cd frontend
npm.cmd run typecheck
npm.cmd run build
```

## Verification Results

- Backend: 101 passed.
- Frontend typecheck: passed.
- Frontend production build: passed.
- Local Alembic head: `20260521_0006`.
- Cloud Alembic scaffold: independent and currently has no cloud business revisions by design.
- Cloud gateway route check: only health route when API docs are disabled.
- Vite emitted a non-blocking chunk-size warning for the existing frontend bundle.
- Pytest emitted non-blocking cache permission warnings in the local Windows environment.

## Known Gaps

- Supabase tables and RLS policies are not implemented in HC0.
- No outbox, inbox, synchronization worker, heartbeat, writer lease, or continuity processing is implemented yet.
- The frontend has reserved cloud/operational environment variables but does not route requests between them yet.
- Local service installation scripts are documented but deferred until the worker exists.

## Next Recommended Phase

HC1: Durable Local Synchronization Foundation. Implement transactional outbox/inbox records, event envelopes, idempotent consumers, checkpoints, retry handling, device identity, and crash-restart tests before accepting cloud QR orders.

