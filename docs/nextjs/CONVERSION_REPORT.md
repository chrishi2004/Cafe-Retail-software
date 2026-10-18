# Kalpvriksh Next.js / Atlas conversion report

Date: 2026-10-18. Branch: `rewrite/nextjs-atlas`. Base: `5d36734d4c104d21f92fc35ac6b7d595bba65187`.

**Status: partial implementation, not complete backend conversion or production acceptance.** The new Next.js application builds and its initial native billing paths pass automated tests. **59** original API operation entries have native subsets and **119** still require native implementation. Even the native subsets require complete request/response/filter/security/domain parity review before replacing the existing product. Unported operations return 501 `migration_pending`.

## Deliverables

- Independent `apps/web` Next.js 16.4.2 / React 19.3.1 / TypeScript application with MongoDB 7.7.0 Node driver. No Vite or FastAPI process is required by this new app; no legacy API proxy is implemented.
- Existing visual components/styles copied into `src/legacy` as the frontend migration source. Browser-only screens use a client boundary; App Router owns navigation and deep links. Old Retail hash bookmarks redirect to new paths. The route catalogue exposes 34 logical screens through the Next catch-all page, rather than claiming 34 separate `page.tsx` files.
- Native credential/TOTP login, signed/revocable sessions and active group/company/branch checks; private server configuration and explicit new-database bootstrap. Server scopes do not trust payload company IDs.
- Native non-GST fully paid counter checkout for both ventures, exact integer-paise/scaled-quantity arithmetic, conditional stock deduction, transactional numbering/invoice/payments/movements and request-key conflict/replay handling.
- Native read-only Café receipt/history subset, immediate-sales Café metrics/CSV, group turnover, stock adjustment/read subset and current-day closing. Existing Café receipt-only 80mm CSS is carried across. Retail currency display preserves cents in the copied helper.
- Detailed [website PRD](WEBSITE_PRD.md), 34-page inventory, all 163 operational/15 cloud operation contracts, OpenAPI snapshots, 474-function/class appendix and explicit native parity CSV.
- Separate `.github/workflows/nextjs-atlas.yml` for repeatable isolated checks. It has not been remotely executed; no push/deployment was performed here.

## Validation performed

Commands below run from `apps/web` unless marked otherwise.

| Command | Result |
| --- | --- |
| `npm install`, followed by lockfile installation/update of patched Playwright 1.55.1 | PASS; lockfile committed |
| `npm run typecheck` | PASS |
| `npm test` | 7 passed: bounded request-body rejection, paise/quantity precision, canonical request identity, India date boundary, password verification, authenticated MFA encryption/RFC TOTP vector, isolated DB naming |
| `npm run test:integration` | 1 comprehensive real disposable MongoDB replica-set test passed; no mocks for database transactions |
| `npm run build` | PASS; Next.js production bundle and TypeScript checks |
| `npx playwright install chromium` | PASS after the downloader's fallback mirror; patched tool/browser version installed |
| `npm run test:browser` | 1 production browser test passed: real Next server → native API → disposable MongoDB → rendered receipt; Retail barcode/checkout also checked |
| `npm audit --json` | PASS: 0 vulnerabilities in new app dependency tree at audit time |
| Root `.venv/bin/python -m pytest backend/tests -q -rs` | 309 passed, 27 skipped, 3 upstream warnings; 170.08 seconds |
| Root `npm --prefix frontend run typecheck` | PASS; preserved frontend |
| Root `VITE_API_BASE_URL=http://127.0.0.1:8000/api npm --prefix frontend run build` | PASS; preserved frontend, existing large-chunk warning |
| Root `node --test frontend/tests/cafe-v1.test.mjs` | 2 passed |
| Root `python scripts/check_cafe_v1_baseline.py` | 396 frozen files verified; no changed/removed original files; valid V1 ancestry |
| Root `.venv/bin/python scripts/inventory_nextjs_rewrite.py` | Generated source inventory without connecting to a business database |

The 27 preserved-backend skips are eight optional PostgreSQL integrations, one original production browser acceptance test and eighteen cloud integrations. They are **not** certified by the new MongoDB tests. Original PostgreSQL restore/migration and physical V1 acceptance remain unverified in this environment. No V1 tag was fabricated.

### Native transaction integration evidence

The disposable MongoDB 7.0.24 replica-set test creates only isolated test data and verifies:

1. New bootstrap and repeat-bootstrap refusal.
2. Owner TOTP login and Café/Retail cashier login.
3. Staff owner-API denial and cross-company header rejection.
4. Restricted public API cannot post a financial record.
5. Scoped catalogue/menu/product setup and opening stock adjustment.
6. Café Cash, UPI, Card checkout, each using the native financial transaction.
7. Concurrent same-key requests return the same invoice; same key/different cart conflicts.
8. Historical receipt read changes no invoice/payment/movement/stock counts; Retail cannot read Café receipt.
9. Two simultaneous sales of the final six units produce one success and one stock conflict; stock ends at zero.
10. Billed sales and collections reconcile to INR 1,000.00.
11. Staff cannot create closing. Owner closing derives INR 900.00 expected cash from INR 100.00 opening plus INR 800.00 cash, with INR 200.00 non-cash.
12. Closed-day checkout is rejected; logout revokes the session.
13. Retail Cash/UPI/Card use separate `RETAIL-` numbering, produce three invoices, replay safely and retain 7/10 opening units.

The production-browser test uses another separate replica set and server on loopback port 4317. It confirms Café login routing, menu selection, invoice creation, payment/stock effects, hidden navigation under print CSS, next customer and logout without a day closure. It then logs in the Retail cashier, scans a barcode through the UI, checks out an INR 50.25 item, verifies `RETAIL-000001` and reconciles its stock.

Print CSS validation is not a physical printer/driver/paper-cut test. No bank/UPI/card terminal transaction was performed. Real Atlas credentials/project connectivity, a Vercel deployment, imported historical records, backup/restore and production hardware are not certified.

### Issues found and resolved during implementation

- The copied legacy entry shim could reintroduce the old portal router. The new runtime imports `RetailApplication` directly and omits the duplicate shim/root copies; original source entrypoints remain intact.
- `tsx` CLI attempted an unavailable Unix IPC socket; test/bootstrap scripts now use Node's supported `--import tsx` invocation.
- Disposable `mongod` could not open its Unix socket in this environment. Test instances now disable that optional socket and use loopback TCP; real transaction tests then passed.
- Initial print assertion looked only at each navigation element's own computed display, missing a hidden ancestor. It now checks layout rectangles under print media, confirming the actual rendered state.
- Playwright 1.55.0 introduced a dependency advisory; the new app was upgraded to 1.55.1 and re-audited to zero reported issues.
- Native financial paths reject unsupported GST, partial/credit/change, customer-linked ledger posting and price override flows rather than silently dropping their business effects.

## Preservation and branch evidence

`main` remains `d9cffb00d24605ba8059d00cede5c56a0b753cf2`; `release/cafe-v1` remains `9ab1eb67cea5d6cb613a582455cc53099834cacc`; `release/full-v2` remains `5d36734d4c104d21f92fc35ac6b7d595bba65187`.

Relative to the preserved base, all changes are additions on `rewrite/nextjs-atlas`: `apps/web/**`, `docs/nextjs/**`, the inventory generator and the new workflow. Original `frontend/**`, `backend/**`, deployment units, backup scripts, migrations and local-only entrypoints are unchanged. No installed runtime configuration, production PostgreSQL database or production Atlas database was accessed. No original Café file/route was removed or renamed. The new app's pending APIs are explicitly documented and are not substituted into the installed application.

## Remaining work before this can be called a complete conversion

Complete the 119 unported operations and full contract parity for the native subsets, including the entire original invoice/tax/customer-ledger/purchase/order/kitchen/QR/governance/reporting/intelligence domains. Extend API failure/role/concurrency tests and production browser coverage accordingly. Design and prove PostgreSQL → MongoDB import with historical reconciliation, authentication conversion, verified backups and restore. Obtain real deployment/provider/device acceptance and approve cutover. The PRD's acceptance matrix is the handoff contract for this work.

## Recovery

This branch has not touched a customer installation. Returning to the preserved branch does not require database rollback. Retain or revert the experimental code with normal Git history; do not reset/rewrite protected releases. Experimental test databases are disposable. If a future web installation accepts real sales, never discard it or rerun bootstrap to fix an upgrade; recover from a verified archive with explicit post-backup loss/reconciliation boundaries and keep the original database intact until approved cutover.
