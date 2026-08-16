# P2 Phase Report: Venture Scope Enforcement, Roles, And Security Context

## Status

- Phase: P2
- Status: Complete
- Date: 2026-08-11
- Base: P1-complete `main`
- Merge commit: `82e7be25fdc7c963527f80f59d17c8d4be6beef3`
- Local Alembic revision: `20260811_0009`
- Cloud Alembic history: unchanged and separate

## Scope Implemented

- Added server-derived `ScopeContext` with business-group, company, branch, role, and permission data.
- Added request-bound `ScopedSession` enforcement for company and branch ORM reads.
- Added write-time company/branch checks and same-company foreign-object validation.
- Added scope coverage for inventory batches, serial numbers, and product price history.
- Added persistent `token_version` access-token claims and database validation so role/company/logout revocation survives process restarts and multiple API instances.
- Added persistent step-up authentication timestamp and `/auth/step-up` foundation.
- Added active business-group/company validation during login and authenticated requests.
- Added non-disclosing 404 handling for cross-company write/reference violations.
- Made audit writes company-scope aware.
- Extended frontend auth typing for business group, company, branch, permissions, and expanded roles without altering the legacy portal structure before P3.
- Kept helper identity rows such as aliased creator/approver users out of the generic business-row loader filter while retaining scope on the authoritative business parent. This avoids alias-invalid SQL without weakening company isolation.

## Verification Results

GitHub Actions workflow `P2 Scope Enforcement Verification`, run `31528002756`, completed successfully against the final PR head `e5bf37a808af27a4f46a9db5fe44a629ee0e5f06`.

Verified:

- PostgreSQL 16 startup and local migrations through `20260811_0009`: passed.
- Local/cloud Alembic history separation: passed.
- P2 security/isolation suite plus auth, scope constraints, HC1 sync, and deployment tests: **29 passed**.
- Ownership-aware development reseed after P2: passed.
- Complete backend regression: **133 passed**.
- Backend compile check: passed.
- Frontend dependency install: passed.
- Frontend typecheck: passed.
- Frontend production build: passed.
- Inherited `P1 Multi-Venture Schema Verification` workflow on the same head: passed.
- Inherited `HC1 Verification` workflow on the same head: passed.

## Required Security Evidence

Automated negative tests prove:

- Cafe Admin receives only Cafe scope from `/auth/me`.
- Persisted `token_version` changes revoke already-issued access tokens.
- Logout persists revocation by incrementing the token version.
- Deactivated company access fails closed.
- Step-up authentication records its successful server-side timestamp and rejects a wrong password.
- Cafe Admin cannot list/fetch Retail products, categories, suppliers, branches, inventory, customers, sales, invoices, purchase orders, forecasts, business profile, dashboard counts, exports, or AI sessions.
- Retail Admin cannot discover Cafe business rows.
- Branch users cannot list another same-company branch.
- Cross-company foreign IDs fail without disclosing the existence of the other venture's object.
- Super Admin remains the only global scope.

## Exit Gate

**P2 exit gate passed.** Backend company/branch authorization is now the hard isolation boundary. No Cafe portal or customer feature needs to trust frontend role hiding or client-supplied company IDs.

## P3 Boundary

P3 now owns the separate Super Admin, Retail, and Cafe portal shells, safe venture/user management APIs, venture labels/selectors, and Cafe staff seed accounts. The temporary P2 frontend compatibility role bridge must be reduced or removed as the real portal router becomes authoritative.
