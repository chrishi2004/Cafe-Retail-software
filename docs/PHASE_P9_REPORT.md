# Phase P9 Report — Cafe and Consolidated Reporting

## Status

P9 is implemented on `phase/p9-cafe-consolidated-dashboards`, based on verified main commit `9e06eb955a14ec482a2a56927ac0766ee9a46c19`.

- Pull request: [#2](https://github.com/chrishi2004/Cafe-Retail-software/pull/2)
- Verification workflow: [run 31964976329](https://github.com/chrishi2004/Cafe-Retail-software/actions/runs/31964976329)
- Scope boundary: P9 only. P10 and P11 were not started.
- Merge state: intentionally unmerged pending review.

## Delivered requirements

### Cafe dashboard

The Cafe dashboard provides date, branch, source-channel, status, payment-mode, menu-category, menu-item, and table filters. It reports:

- order count and ordered value;
- billed and net billed revenue;
- collections and outstanding;
- average bill value;
- cancelled unbilled value and reserved void value;
- top items, source mix, payment mix;
- table-session turnover and open/unbilled sessions.

Cancelled unbilled orders are excluded from billed revenue. Invoice-linked Cafe sales are represented by their invoice source once, preventing double counting.

### Consolidated dashboard

The Super Admin dashboard exposes the active scope label and supports All Ventures or an explicitly selected venture. Venture summaries include billed revenue, net billed revenue, collections, and outstanding. Consolidated net billed revenue reconciles to the sum of the selected Retail and Cafe venture totals.

### Reporting views and exports

Migration `20260816_0017` adds:

- `vw_cafe_order_summary`
- `vw_cafe_order_items`
- `vw_cafe_table_turnover`
- `vw_cafe_billing_reconciliation`
- `vw_cafe_payment_summary`
- `vw_venture_sales_summary`
- `vw_business_group_turnover`

Cafe CSV output is Cafe-scoped. Consolidated CSV output includes venture identity, company identity, revenue, collections, and outstanding columns.

### AI

The Cafe AI tools are database-backed and scope-aware:

- `get_cafe_sales_summary`
- `get_open_table_sessions`
- `get_pending_cafe_orders`
- `get_cafe_payment_reconciliation`
- `get_cafe_top_items`
- `get_cafe_cancelled_items`
- Super Admin-only `get_venture_comparison`

ScopeContext is passed through the AI route. Non-Super Admin users cannot switch venture scope or obtain cross-venture comparison data. Deterministic database-backed responses remain available without an OpenAI key.

### Frontend

Added the Cafe dashboard and Super Admin consolidated dashboard surfaces with visible scope labels, loading states, error states, empty top-item state, KPI cards, reconciliation details, and venture comparison.

## Changed files

- `backend/app/schemas/p9.py`
- `backend/app/services/p9_reporting.py`
- `backend/app/services/ai.py`
- `backend/app/api/routes/dashboard.py`
- `backend/app/api/routes/exports.py`
- `backend/app/api/routes/ai.py`
- `backend/alembic/versions/20260816_0017_p9_reporting_views.py`
- `backend/tests/p9_fixtures.py`
- `backend/tests/test_cafe_dashboard.py`
- `backend/tests/test_consolidated_dashboard.py`
- `backend/tests/test_multi_venture_exports.py`
- `backend/tests/test_cafe_ai_scope.py`
- `frontend/src/api/p9.ts`
- `frontend/src/pages/CafeDashboardPage.tsx`
- `frontend/src/pages/ConsolidatedDashboardPage.tsx`
- `frontend/src/portals/CafePortal.tsx`
- `frontend/src/portals/SuperAdminPortal.tsx`
- `.github/workflows/p9-verification.yml`

## Security and reconciliation evidence

The green P9 workflow verifies:

- Cafe-only dashboard and export output contains no Retail data;
- Super Admin Cafe filtering equals the Cafe source total;
- consolidated net billed revenue equals Retail plus Cafe source totals;
- cancelled unbilled Cafe orders do not enter billed revenue;
- unpaid billed invoices affect outstanding rather than collections;
- payment rows reconcile to invoice-linked collections;
- invoice-linked Cafe sales are counted once;
- consolidated exports include explicit venture identity;
- Cafe AI cannot switch venture or disclose data outside the active Cafe scope.

## Verification results

The final green workflow run passed:

- required P9 tests: `test_cafe_dashboard.py`, `test_consolidated_dashboard.py`, `test_multi_venture_exports.py`, `test_cafe_ai_scope.py`;
- P2 cross-venture security tests;
- Retail invoice, payment, stock, ledger, dashboard, export, and AI regression tests;
- HC1, HC2, HC3, and HC4 compatibility tests;
- full backend regression;
- backend compilation;
- frontend portal boundary verification;
- frontend typecheck;
- frontend production build.

## Known gaps and boundaries

- Void and refund workflows remain represented as reserved/reporting fields where the current domain model has no complete P9 refund ledger.
- Expected cash variance and operational reconciliation workflows remain future work.
- Low-stock links are not added to the P9 Cafe dashboard because inventory alerting remains in existing operational surfaces.
- AI write actions and model-provider enhancements remain outside P9.
- No P10 or P11 work is included.

## Next phase

The next planned phase is P10, subject to review and merge of this P9 pull request. P10 must not begin until P9 is approved and merged.
