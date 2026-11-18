# Product readiness

## Implemented

- Café and Retail POS, invoices, payments and receipt history
- Inventory, low-stock, purchasing and stock intake
- Café menu, tables, QR ordering, kitchen workflow and closing
- Customers, credit ledger, staff roles, MFA and session revocation
- Expenses, refunds, audit history, exports, dashboards and profit/loss
- Hosted Next.js API and UI backed only by MongoDB Atlas
- Patched Next.js `16.4.6`; dependency audit reports zero known vulnerabilities
- Automated type, unit, MongoDB integration, production build and browser gates

## Required before merging this cleanup to production

- Verify the Vercel preview with a separate non-production Atlas database
- Complete cashier, waiter, kitchen and owner acceptance on real shop devices
- Prove Atlas backup and restore, monitoring and capacity alerts
- Validate the receipt printer, barcode scanner and customer QR flow
- Protect `main` and release only the exact tested staged build

## Remaining Café product work

- Managers can enable recipe consumption per menu item. Billing deducts ingredients and records their current catalogue costs on the invoice. Orders retain their recipe at placement. Existing menu items retain their previous billing behavior. Confirm this timing and cost basis with the shop before enabling it.
- Stock Feed receives ingredients from suppliers, values purchases and optionally records the associated expense.
- Confirm kitchen tickets, bill edits, discounts and closing policy with staff

## Remaining Retail product work

- Inventory supports branch transfers, damage write-offs and physical counts. Partial invoice returns, exchanges and customer credit adjustments require a return policy.
- Retail receiving records lot balances. Checkout allocates the earliest expiry first and excludes expired lots. Managers can classify existing on-hand stock before enabling mandatory recorded lots per product. Confirm physical picking follows the recorded batch.
- Product management prints Code 128 labels for existing barcodes. Confirm physical scanner/printer compatibility.

## Business and operational acceptance

- Obtain accountant acceptance for statutory GST documents when GST is enabled
- Define incident ownership, alerting, restore drills and a rollback checklist
- Confirm Vercel and Atlas plans permit the intended production usage and load

The former Local Hub system is available in the private archive if an offline
deployment is required in the future.
