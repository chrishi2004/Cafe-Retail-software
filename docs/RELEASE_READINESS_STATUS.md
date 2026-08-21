# Release Readiness Status

Status: active release-remediation branch.

This document records the current implementation truth for deployment. It exists because several older planning documents still contain historical phrases such as `implementation not started`. Those phrases describe their state when authored and must not be interpreted as the current repository state.

## Implemented foundation

The repository already contains the multi-venture Retail/Cafe implementation phases P1-P11 and hybrid continuity phases HC0-HC4, including:

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

## Release-remediation sequence

### R5 — contract reconciliation

- Freeze the final operating model.
- Record current implementation truth.
- Treat older `implementation not started` phrases as historical.

### R6 — cloud-primary customer path

- Public Cafe route uses Cloud Gateway directly in normal operation.
- Customer order submission remains idempotent and durable.
- Add cloud-safe bill-request command; final billing remains local.
- Preserve cloud/local identity and status convergence.

### R7 — Linux Local Hub production profile

- systemd-managed API, sync worker, local frontend, backup/health checks and tunnel integration.
- PostgreSQL private binding and stable LAN access.
- automatic restart/recovery after host reboot.

### R8 — production-like concurrency/failure evidence

- duplicate customer submit;
- duplicate cloud delivery;
- concurrent table ordering;
- concurrent billing;
- last-stock race;
- internet failure before/after local commit;
- Hub restart and queue drain;
- cloud outage while local POS continues;
- backup/restore preservation of queue/checkpoint state.

### R9 — public-production security gate

- TOTP/MFA for privileged admin exposure;
- trusted-proxy behavior;
- edge/application rate-limit evidence;
- dependency audit;
- browser E2E/viewport coverage;
- PostgreSQL private-binding evidence;
- disposable backup/restore drill.

## Definition of release-ready

Do not claim public production readiness until all release blockers above have either automated green evidence or documented real-environment evidence. Passing unit tests alone is insufficient for networking, browser, backup/restore, or provider configuration claims.
