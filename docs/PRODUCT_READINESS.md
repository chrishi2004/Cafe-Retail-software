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

- Implement Café ingredient recipes, consumption, waste and reliable COGS
- Add supplier purchase/receiving workflows tailored to Café ingredients
- Confirm kitchen tickets, bill edits, discounts and closing policy with staff

## Remaining Retail product work

- Implement Retail returns/exchanges, stock disposition and branch transfers
- Complete batch/expiry workflows where the shop requires them
- Validate barcode coverage, labels, credit collection and stock-count workflow

## Business and operational acceptance

- Obtain accountant acceptance for statutory GST documents when GST is enabled
- Define incident ownership, alerting, restore drills and a rollback checklist
- Confirm Vercel and Atlas plans permit the intended production usage and load

The former Local Hub system is available in the private archive if an offline
deployment is required in the future.
