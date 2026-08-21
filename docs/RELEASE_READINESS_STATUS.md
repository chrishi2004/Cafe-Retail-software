# Release Readiness Status

Status: repository release-remediation implementation complete on `agent/release-readiness-finalization`; real-environment go-live evidence still required before public production.

This document records the current implementation truth for deployment. Several older planning documents contain historical phrases such as `implementation not started`; those describe their state when authored and must not be interpreted as the current repository state.

## Implemented foundation

The repository contains the multi-venture Retail/Cafe implementation phases P1-P11 and hybrid continuity phases HC0-HC4, including:

- venture/company/branch scope and role isolation;
- Retail and Cafe portals plus Super Admin scope switching;
- Cafe menu, tables, QR, staff ordering and kitchen workflow;
- Cafe billing over the shared invoice/payment/inventory/ledger engine;
- consolidated dashboards and scope-aware AI/reporting;
- local PostgreSQL authority;
- independent cloud coordination schema/migrations;
- durable outbox/inbox/checkpoint/dead-letter synchronization;
- cloud Cafe order intake and Local Hub convergence;
- heartbeat, writer lease/fencing, restart/recovery, and continuity state;
- security headers, production configuration checks, auth throttling, and release-gate documentation.

## Final deployment contract

`docs/FINAL_PRODUCT_OPERATING_MODEL.md` is authoritative for request routing and deployment topology.

- Customer QR/menu/order/status/bill-request: cloud-primary.
- POS/waiter/kitchen/billing/inventory/purchases/AI operational tools: Local Hub.
- Final invoice/payment/ledger/stock/audit authority: Local PostgreSQL only.
- Remote Super Admin: hosted UI -> authenticated HTTPS tunnel/private network -> Local Hub for live operations.
- Cloud snapshot fallback, where present: read-only/sanitized/stale-labelled; never a silent financial writer.

## Release-remediation results

### R5 — contract reconciliation: implemented

- Final operating model frozen.
- Current implementation truth recorded.
- Older `implementation not started` text explicitly treated as historical where it conflicts with release status/topology.

### R6 — cloud-primary customer path: implemented

- Hosted public Cafe route now opens Cloud Gateway sessions directly instead of Local-Hub-first fallback.
- Customer cloud order submission remains durable and idempotent.
- Cloud bill request uses its own durable coordination table and independent `cafe_bill_request` aggregate so it cannot collide with Cafe order aggregate versions.
- Local Hub bill-request handler changes only table-session state; it does not create invoice, payment, ledger, sale, or stock effects.
- Bill-request browser retry keys are scoped to the target cloud order so a later table session cannot collide with an older request.
- Regression coverage proves duplicate delivery safety and zero cloud bill-request financial effects.

Expected cloud migration head: `20260821_cloud_0003`.

### R7 — Linux Local Hub production profile: implemented in repository

- systemd-managed Local Hub API, durable sync worker and local React PWA.
- scheduled verified PostgreSQL dump job and health-check script.
- automatic service restart/recovery after host reboot.
- Linux/Omarchy deployment runbook, private PostgreSQL boundary and stable LAN guidance.

Physical Hub installation, firewall, UPS and real network evidence remain deployment-time checks.

### R8 — concurrency/failure evidence: automated coverage extended

Inherited suites already cover duplicate cloud delivery, worker restart, billing idempotency, stock safety, recovery, reconciliation and cross-venture isolation. Release remediation adds explicit cloud bill-request convergence coverage and the consolidated Release Readiness workflow.

Real multi-device LAN, printer, router/internet interruption and power/UPS exercises remain physical go-live evidence because CI cannot emulate the actual cafe environment.

### R9 — public-production security gate: implementation completed; environment evidence required

Implemented:

- TOTP MFA persistence and encrypted secret handling;
- hashed one-time recovery codes;
- production-default privileged MFA requirement for Super Admin/Venture Admin;
- MFA-aware login and step-up authentication;
- authenticated enrollment/confirmation/disable endpoints;
- trusted-console privileged MFA bootstrap for first production enrollment;
- browser login support for authenticator/recovery code;
- MFA unit/integration tests;
- Chromium release smoke tests;
- Python/npm dependency-audit steps;
- disposable PostgreSQL backup/restore proof in Release Readiness CI;
- Linux deployment script syntax/compile checks;
- explicit go-live checklist for trusted proxy/edge rate limiting/private database/provider configuration.

Expected Local Hub migration head: `20260821_0019`.

## Automated release gate

`.github/workflows/release-readiness.yml` is the consolidated release gate. It performs:

- Local Hub and cloud migrations against independent PostgreSQL databases;
- release-head verification;
- targeted MFA/synchronization/billing/isolation tests;
- complete backend regression;
- Python compile and Linux shell syntax checks;
- Python dependency audit;
- verified `pg_dump` creation, checksum and disposable restore;
- frontend secret scan, typecheck and production build;
- headless Chromium release smoke;
- production npm dependency audit.

A successful Vercel build alone is not enough to declare release readiness. The Release Readiness workflow must be green for the exact commit that is deployed.

## External go-live evidence still required

Repository code cannot prove the following until the real environment exists:

- actual Supabase/Vercel production URLs and secrets are configured correctly;
- production cloud and local migrations were applied to the intended databases;
- physical Local Hub boots all managed services automatically;
- PostgreSQL TCP 5432 is not publicly reachable;
- approved HTTPS tunnel/private-network path reaches only the Operational API;
- privileged production accounts are actually enrolled in MFA;
- provider/edge rate limits are configured;
- real POS/waiter/kitchen devices work concurrently on the cafe LAN;
- printer/peripheral behavior is correct if used;
- internet outage, Hub reboot, UPS/power recovery and queue drain work on the deployed hardware;
- real backup copy is stored independently and successfully restored;
- remote Super Admin reaches live Local Hub data through the approved route.

Use `docs/PRODUCTION_GO_LIVE_CHECKLIST.md` to collect this evidence.

## Release decision

The repository-side remediation is implementation-complete on the release branch. Do **not** label the physical/provider installation `PUBLIC PRODUCTION READY` until the consolidated automated gate is green and every applicable real-environment item in the production go-live checklist has been evidenced for the exact deployed commit.
