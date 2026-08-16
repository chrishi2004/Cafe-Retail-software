# P6 Phase Report: Cloud-Backed Customer QR Ordering

## Status

- Phase: P6
- Status: Complete and verification-reconciled
- Verification date: 2026-08-16
- Verified source commit: `0dd520aef37741f50094e2e5331346c74b0f03fe`
- GitHub Actions run: [P6 Customer QR Ordering Verification #1](https://github.com/chrishi2004/Cafe-Retail-software/actions/runs/31961302654)
- Run conclusion: success

## Scope Verified

P6 connects the public Cafe QR ordering surface to the approved cloud coordination boundary while keeping authorization, pricing, idempotency, and Local PostgreSQL authority intact.

The verified implementation covers:

- Public Cafe QR menu/session access.
- Server-validated QR/table sessions.
- Published Cafe menu and availability boundary.
- Server-authoritative item snapshots and pricing.
- Idempotent public order submission using `Idempotency-Key`.
- Public-order rate limiting.
- Safe order references and customer-facing status behavior.
- Cross-venture and company/branch authorization boundaries.
- Reuse of the Cafe order domain without granting public access to Retail data.
- Local PostgreSQL remaining authoritative for financial, inventory, stock, ledger, and audit effects.

P6 does not create invoices, payments, stock movements, or inventory effects. Those remain later Local Hub responsibilities.

## Migration Boundary

- Local migration history retains P6 revision `20260813_0013`.
- Cloud coordination history retains `20260813_cloud_0001`.
- Local and cloud migration heads remain separate.
- The verification applied the current local head and confirmed the P6 revision remains in history.

## Verification Evidence

The successful GitHub Actions workflow verified:

- PostgreSQL migration through the current local head.
- Separate cloud migration history.
- Public QR order creation.
- Public QR authorization and expired/revoked-session behavior.
- Duplicate submission/idempotency behavior.
- Public rate limits.
- Cafe QR security.
- Table-session behavior.
- Cross-venture isolation.
- Company-scope authorization.
- Existing inventory and invoice regression.
- HC1 synchronization foundation compatibility.
- Deployment-mode route behavior.
- Complete backend regression.
- Backend compilation.
- Frontend public-order boundary checks.
- Authenticated portal boundary verification.
- Frontend TypeScript typecheck.
- Frontend production build.

## Security Controls Verified

- Public QR requests cannot select arbitrary company, branch, price, tax, or payment state.
- QR/session scope is server-derived and fails closed when invalid.
- Public clients cannot discover Retail records or counts.
- Public order retries do not create duplicate orders.
- Server-side pricing and menu snapshots are used.
- Local-only financial and inventory routes remain outside the public cloud surface.
- No browser bundle contains server-only cloud credentials.

## Known Documentation Gap Resolved

This report was missing from the uploaded repository snapshot. It has now been added from the repository implementation, P6 workflow definition, test list, migration checks, and successful run evidence. No unsupported test count or historical PR claim is added.

## Next Dependency

HC3 and the later P7/P8/HC4 gates remain required and were separately verified successfully on the same source commit.
