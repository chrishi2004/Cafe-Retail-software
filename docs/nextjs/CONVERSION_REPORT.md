# Kalpvriksh Next.js / Atlas conversion report

Current branch: **main**. Baseline: `9a80860d2db2744f6391744100d542b6640c5580`.

The initial rewrite's 59-subset/119-pending inventory has been superseded by the native web implementation. Read [NATIVE_COMPLETION_REPORT.md](NATIVE_COMPLETION_REPORT.md) for the current service coverage, exact validation results, intentional Local Hub interface retirement and production limits.

Current source operation classifications are 158 native web service entries, five single-database status/reconciliation replacements, and 15 retired Local Hub interfaces. The shared health entry is duplicated across the source operational/cloud inventories. No full legacy parity or production acceptance claim is made.

The website has 35 logical screens and deploys as one Next.js project from `apps/web`. Existing accounts/database secrets must be retained across updates; bootstrap is only for an empty database.

The original Café source and release branches are preserved. No live database was imported, reset or reseeded. The inherited Python regression has one independently reproduced UTC/India date-boundary failure, documented in the current report; it has not been silently marked passed.
