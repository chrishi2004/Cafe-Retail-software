# P1 Phase Report: Ownership, Venture, And Data-Scope Schema

## Status

- Phase: P1
- Status: Complete
- Date: 2026-08-11
- Base: HC1-complete `main` at `198db73607e4dbb2c348285ad5597db20b4dc10c`
- Merge commit: `eed250eb51d23f67a9789b1d8c8f8dba999a0ab2`
- Local Alembic revision: `20260811_0008`
- Cloud Alembic history: unchanged and separate

## Scope Implemented

- Added `BusinessGroup -> Company -> Branch` ownership hierarchy.
- Added Retail/Cafe venture type, stable slug, demo flag, and ownership group to companies.
- Added business-group/company scope and token-version/security fields to users.
- Added roles: Super Admin, Venture Admin, Store Manager, Staff, Order Taker, Kitchen, Analyst.
- Added company scope to operational/confidential roots required by the multi-venture TRD.
- Converted branch, category, supplier, SKU, barcode, sale number, PO number, customer identity, and invoice number uniqueness to company-aware constraints.
- Added expand/backfill/validate PostgreSQL migration preserving legacy IDs, financial totals, and business identifiers.
- Promoted the legacy global Admin to Super Admin during migration while temporarily preserving old global-admin capabilities until P2 installs `ScopeContext` authorization.
- Added a multi-venture-safe development seed entry point that creates one Business Group, one Retail venture, and a minimal Cafe venture/branch before generating existing Retail demo data.
- Preserved HC1 sync tables and separate cloud migration history.

## Verification Results

GitHub Actions workflow `P1 Multi-Venture Schema Verification`, run `31524427525`, passed against the merge candidate.

Verified:

- PostgreSQL 16 startup and health check: passed.
- Upgrade through HC1 (`20260811_0007`): passed.
- Legacy preservation fixture insertion: passed.
- P1 migration `20260811_0008`: passed.
- Legacy IDs, sale/invoice identifiers, and financial totals after backfill: preserved.
- Local migration head: `20260811_0008`.
- Cloud migration history: separate and unchanged.
- P1 targeted + HC1/deployment/Retail regression set: **64 passed**.
- Multi-venture development reseed: passed with 1 business group, 2 companies, 3 Retail branches, 1 Cafe branch, 70 products, 6,635 sales, 2 invoices, and 6 users.
- Complete backend regression: **120 passed**.
- Backend compile check: passed.
- Frontend dependency install: passed.
- Frontend typecheck: passed.
- Frontend production build: passed.
- Independent `HC1 Verification` workflow on the same PR head: passed, confirming P1 did not regress the durable synchronization foundation.

## Exit Gate

**P1 exit gate passed.** Ownership and company-scope schema now exist and existing Retail identifiers/totals survive the backfill.

P1 does **not** claim route-level cross-venture isolation. P2 remains release-blocking before any Cafe portal or customer feature is started.

## P2 Boundary

P2 must replace branch-only authorization with shared `ScopeContext`, enforce company/branch predicates on every service/query, validate referenced foreign objects against the active company, add persistent token-version revocation checks, and pass negative Retail/Cafe isolation tests before P3 begins.
