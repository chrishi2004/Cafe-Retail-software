# Café V1 local operational release

Branch: `release/cafe-v1`.

## Daily operation

- Café Staff and Order Taker accounts land on `/cafe/pos`. Both require a valid Café branch assignment. Café Admin accounts land on `/cafe/dashboard`; the group owner retains the existing venture chooser and opens the Café dashboard from it.
- Search the menu, add items, change quantities, choose Counter or Takeaway, and select an active Cash, UPI or Card mode. Enter a payment reference when required by that mode. **Pay & create invoice** prices and settles the order on the server. The paid receipt appears immediately; **Next customer** starts an empty bill.
- Menu prices are estimates until checkout. The existing Café billing engine remains authoritative for invoices, payment records, sales, stock availability and stock movements. Linked products reduce inventory; prepared menu items without a product link retain the existing no-stock-movement behaviour.
- An interrupted checkout stays in browser session storage. Use **Retry same sale** to retrieve its invoice without creating a second sale. Keep the browser tab/session available until an uncertain sale is resolved. A new customer receives a new checkout key.
- Logging out revokes only the login session. It does not submit or close Daily Closing.

## Owner dashboard and reports

The dashboard defaults to Today in Asia/Kolkata and refreshes every 30 seconds. It shows order count, billed sales, collections, Cash/UPI/Card totals, outstanding, average bill, top billed items and current open orders (up to the existing 200-order list limit). Existing ordered-item reports remain available separately.

Reports offer Today, Yesterday, 7 Days (including today), This Month, Last Month and Custom Range. CSV export uses the selected valid range. Collections follow the payment date, including receipts against older invoices; billed sales follow the invoice date. Average bill excludes cancelled/returned invoices. Reporting and closing use the same Asia/Kolkata midnight boundary.

## Daily Closing

Only Café Admin / scoped group owner can open, submit, close or reopen the day. The page lists authorized active branches by name and restores an existing closing record after reload.

1. Choose the Café branch and record opening cash.
2. Reconcile live cash collections and non-cash totals; enter counted cash.
3. Submit the count. Expected cash and variance are recalculated from source payments at submission.
4. Close the day. Submitted/closed days block new Café billing and additional Café invoice collections for that day. A previously successful checkout can still be retrieved safely.
5. Reopen a submitted/closed day with a correction reason when necessary, then reconcile and submit again.

Expected cash = opening cash + cash collections − recorded cash refunds − recorded cash expenses. Variance = counted cash − expected cash. Counted cash does not rewrite payment records.

## Local setup and preservation

Use the existing local-hub installation, migrations, backup scripts and database; this release does not replace or reset business data and adds no database migration. Configure the real Café company, active branch, employee assignments, menu, existing Café business profile, invoice sequence and payment modes before operational use. The existing Café engine currently requires its supported non-GST configuration; no separate GST billing engine is introduced here. Cash/UPI/Card records confirm cashier-entered collections; they do not integrate with a bank or card terminal.

Retail, QR ordering, cloud continuity, AI and other future modules remain in the repository. The existing table-order page is retained as **Table Order** for operational roles that already support it. This release adds no QR/cloud/AI/Retail capability.

## Validation

- Backend suite: 244 passed, 18 skipped (existing external-database/environment-dependent checks).
- Additional final focused backend run: 16 passed, including the final billed-item reporting changes.
- Frontend routing/date regressions: `node --test frontend/tests/cafe-v1.test.mjs` — 2 passed.
- `npm run typecheck` and `npm run build` in `frontend` — passed. Vite retains a non-blocking size warning for the existing Retail application chunk.
- Chromium against the production frontend and actual local FastAPI/SQLite database: cashier login → menu → paid invoice → next customer → logout → owner login/dashboard → date presets → CSV download → authorized branch closing → submit → close → reload. All passed; no browser runtime errors.

The browser/database smoke check uses isolated test data, not a customer installation. PostgreSQL concurrency and physical receipt-printer acceptance still need verification on the deployment hardware; the automated environment-dependent database tests were skipped.

## 80mm thermal receipts and reprinting

Use **Print receipt** after a Café POS checkout or existing table/takeaway billing. **Receipt history** is available to Café Staff, Order Taker, Store Manager, Admin and a group owner operating in the Café venture. Kitchen and Analyst roles cannot read or reprint Café invoices.

History supports invoice-number search, authorized branch selection, date range and pagination. **View / reprint** retrieves the existing receipt; **Reprint receipt** opens the browser print dialog. Both the history and receipt retrieval endpoints are authenticated GET requests. Reprinting does not invoke checkout, create invoices/payments or change stock/accounting records. Cancelled and partially paid invoice statuses remain visible on the receipt, and outstanding balance appears when nonzero. Reprints are marked **REPRINT** and retain the original invoice number and issue time.

The receipt uses the configured company trade name/name and branch name from the existing Café receipt API. It includes invoice/date/time (IST), item/quantity/unit price/line total, grand total, payment modes, amount paid and applicable balance. The same component is used for original receipts and reprints.

Printer setup:

1. Install/select the actual **80mm thermal printer** and its 80mm roll paper profile.
2. Use 100% scale, one page per sheet, and disable browser headers/footers. Avoid "fit to A4" or Letter.
3. Print one short and one long receipt on the deployment printer to confirm cutting and paper-feed settings. Driver settings may override browser page dimensions.

Print CSS uses a named 80mm page with 4mm margins (72mm content). A dedicated print copy lives outside the app layout; print media hides every other body child, including navigation and buttons. The measured receipt height sets the roll length, with a valid fixed-size CSS fallback for drivers that ignore custom lengths. No PDF generation is involved.

Validation for printing: 10 targeted history/checkout tests passed; 10 existing billing/stock/idempotency/non-GST/history tests passed; frontend typecheck and production build passed. Two Chromium print-layout regressions passed (including an 80-item receipt), as did the real local API/database browser flow: double-click checkout, original print, history selection and three reprints with unchanged financial/inventory tables and no browser runtime errors. Physical printer acceptance remains a deployment step.
