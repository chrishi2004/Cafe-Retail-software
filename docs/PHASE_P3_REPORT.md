# P3 Phase Report: Shared Login, Isolated Portals, And Venture User Management

## Status

- Phase: P3
- Status: Complete
- Date: 2026-08-13
- Base: P2-complete `main`
- Verified implementation head: `ec24df03aaea6e850fa6ab44270fdfb8fa375151`
- Merge commit: `db01e4a6467db10db5d83349b07146e9572b7e84`
- Local Alembic head: `20260811_0009` (no new local schema migration required by P3)
- Cloud Alembic history: unchanged and separate

## Scope Implemented

- Extended `/auth/me` with safe current venture name, slug, business type, company ID, branch ID, server role, and permissions.
- Added current-venture and Super Admin venture-list APIs.
- Added Super Admin-only venture user list/create/reassignment APIs.
- Enforced one company assignment for normal users and no company/branch assignment for Super Admin.
- Validated every user branch assignment against the selected company and rejected branch-required operational identities before issuing access tokens.
- Incremented `token_version` whenever a user role/company/branch/active assignment changes so old sessions fail closed.
- Added server-enforced Super Admin venture selection using `X-Venture-Id`; the selected venture is validated against the Super Admin business group and converted into the same P2 `ScopeContext` used by business queries.
- Added deterministic Cafe Partner Admin, Manager, Order Taker, Kitchen, and Analyst seed accounts.
- Added authoritative frontend portal routing from backend `server_role` and `company_business_type`.
- Added isolated `/super-admin/*`, `/retail/*`, and `/cafe/*` portal surfaces.
- Added a Super Admin venture selector that can enter Retail or Cafe with server-enforced selected scope, while the Super Admin home remains all-venture.
- Added role-aware Cafe placeholder navigation; Kitchen receives preparation-only navigation and Order Taker receives order-only navigation.
- Preserved the existing Retail application inside the `/retail` shell rather than rewriting its operational modules in P3.
- Kept `/order/:qrToken` separate from authenticated portals but intentionally disabled actual ordering until P5, HC2, and P6 gates pass.

## Verification Result

The exact P3 implementation head `ec24df03aaea6e850fa6ab44270fdfb8fa375151` passed all inherited and P3-specific GitHub Actions gates before merge:

- P3 Portal And Venture User Verification: run `31682360462` passed backend and frontend jobs.
  - PostgreSQL migration through local head `20260811_0009` passed.
  - Local/cloud migration history separation passed.
  - Ownership-aware Retail/Cafe seed plus all Cafe role seeds passed.
  - P3 targeted portal, venture-user, branch-assignment, cross-venture, auth/scope, HC1 sync, and deployment-mode tests passed: 53 tests.
  - Complete backend regression passed.
  - Backend compile passed.
  - Frontend portal-boundary verifier, typecheck, and production build passed.
- HC1 Verification: run `31682360461` passed, including HC1 targeted durability/deployment tests and full backend regression.
- P1 Multi-Venture Schema Verification: run `31682360350` passed, including legacy-data preservation, PostgreSQL migration/reseed, targeted tests, and full regression.
- P2 Scope Enforcement Verification: run `31682360393` passed, including cross-venture isolation/security tests, seed verification, and full regression.

## Security Repairs Proven During Verification

- Fixed Super Admin venture selection so selecting Cafe cannot expose Retail business rows.
- Added and enforced `X-Venture-Id` only for validated Super Admin venture selection; normal users cannot switch ventures.
- Added fail-closed handling for invalid legacy operational users without required branch assignments.
- Added branch-assignment tests to the P3 release gate rather than relying only on the full regression suite.
- Cleared selected venture state across login/logout so one authenticated identity cannot inherit another session's venture selection.

## P4 Boundary

P4 owns Non-GST-default behavior, registration/effective-date state, controlled Super Admin GST activation with recent step-up authentication, customer-output privacy, and non-retroactive tax-mode rules. P3 does not alter tax calculation behavior.
