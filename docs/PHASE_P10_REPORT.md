# Phase P10 Report — Daily Closing, Audit, Void, and Controlled Purge

## Status

P10 is implemented on `phase/p10-closing-audit-purge`, based on merged P9 main commit `dfdd8162007293bf0034c85291964a1aaf57814f`.

- Pull request: [#3](https://github.com/chrishi2004/Cafe-Retail-software/pull/3)
- Verification workflow: [P10 run 31968392593](https://github.com/chrishi2004/Cafe-Retail-software/actions/runs/31968392593)
- Scope: P10 only. P11 has not started.
- Merge state: draft and unmerged pending review.

## Files changed

- `backend/app/models/governance.py`
- `backend/app/models/audit_log.py`
- `backend/app/models/__init__.py`
- `backend/app/schemas/governance.py`
- `backend/app/services/governance.py`
- `backend/app/api/routes/governance.py`
- `backend/app/main.py`
- `backend/alembic/versions/20260817_0018_p10_governance.py`
- `backend/tests/test_business_day_closing.py`
- `backend/tests/test_financial_voids.py`
- `backend/tests/test_purge_workflow.py`
- `backend/tests/test_purge_authorization.py`
- `backend/tests/test_audit_immutability.py`
- `frontend/src/api/governance.ts`
- `frontend/src/pages/CafeClosingPage.tsx`
- `frontend/src/pages/PurgeReviewPage.tsx`
- `frontend/src/portalRouting.ts`
- `frontend/src/portals/CafePortal.tsx`
- `frontend/src/portals/SuperAdminPortal.tsx`
- `.github/workflows/p10-verification.yml`

## Requirements implemented

### Daily closing

- Company/branch/date-unique business-day closing records.
- Opening cash, cash collections, cash refunds, cash expenses, expected cash, counted cash, non-cash total, and variance fields.
- `open -> submitted -> closed -> reopened` lifecycle.
- Cash and non-cash payments remain separate.
- Branch/company scope is enforced through ScopeContext.
- Reopening requires an authorized role, a non-empty reason, and audit evidence.

Formula:

`expected_cash = opening_cash + cash_collections - cash_refunds - cash_expenses`

`variance = counted_cash - expected_cash`

### Audit and reversal foundation

- Branch-scoped audit evidence was added.
- Invoice voids are reasoned, scoped, transactional, and idempotent by caller-provided idempotency key.
- Original invoice status is retained as cancelled; a linked FinancialReversal records actor, amount, reason, and compensation requirements.
- No generic financial DELETE endpoint was added.

### Controlled purge

- Purge requests are allowlisted to demo Cafe orders.
- Requests require a non-empty reason, explicit entity, and backup reference.
- Dependency checks reject billed orders and orders linked to table sessions.
- Only Super Admin can request, approve, and execute.
- Recent password step-up is required for approval and execution.
- Requester cannot approve their own request.
- Typed confirmation is bound to the request ID.
- Completed demo purge writes an immutable tombstone and audit event before deleting only the approved order graph.
- Audit and tombstone delete endpoints do not exist.

### Frontend

- Cafe daily closing page exposes expected cash, non-cash totals, counted cash, variance, and lifecycle actions.
- Super Admin purge review page exposes only the allowlisted demo-order workflow and does not expose SQL or arbitrary table names.
- Portal routing limits daily closing to authorized Cafe roles.

## Verification

The green P10 workflow passed:

- required P10 tests;
- P9 dashboards, exports, and AI tests;
- P2 cross-venture security tests;
- Cafe billing/payments and Retail invoice/inventory/ledger/dashboard/export regressions;
- HC4 reconciliation/recovery compatibility checks;
- full backend regression;
- backend compilation;
- frontend P10 boundary checks;
- frontend typecheck;
- frontend production build.

## Security evidence

- Cafe Partner purge attempt returns forbidden.
- Unknown purge entity types are rejected.
- Invalid step-up credentials are rejected.
- Purgable records must be demo-company data and have no billed or table-session dependencies.
- Purge approval/execution requires a recent step-up grant.
- Audit/tombstone deletion routes are absent.
- Governance queries validate company and branch scope before acting.

## Known gaps and limitations

- The current phase records the required payment, stock, and ledger compensation obligations in the FinancialReversal evidence object; complete domain-specific refund, stock-movement, and ledger-compensation handlers should be expanded before production financial use.
- Closed-day mutation blocking is not yet wired into every existing invoice, payment, stock, and ledger write service.
- Backup-reference validation confirms a recorded reference, but an external backup verifier is not connected in this repository.
- Optional second-person approval is represented in the request model but is not enabled by a configurable policy yet.
- The purge allowlist intentionally covers only demo Cafe orders; no Retail or issued-financial purge path is exposed.
- P11 security hardening and release packaging have not started.

## Next phase

P11 — Security Hardening, End-to-End QA, and Release Packaging — may begin only after P10 review resolves the listed production limitations and this PR is approved and merged.
