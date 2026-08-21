# Final Product Operating Model

This document is the release-time product boundary for the Kalpvrik Retail and Cafe suite.
It keeps the user experiences separate while reusing one repository, one design system,
and one set of verified business rules.

**Release precedence:** for deployment topology and user request routing, this document
supersedes older planning text that describes the Cafe customer route as Local-Hub-first
or says the multi-venture/hybrid implementation has not started. Existing PRD/TRD rules
for financial authority, stock integrity, venture isolation, auditability, idempotency,
and recovery remain mandatory.

## User-facing applications

The frontend uses one low-cost hosted React deployment with isolated route surfaces.
They may later receive separate custom domains without splitting the codebase.

| Surface | Route | Audience | Authentication | Primary API target |
| --- | --- | --- | --- | --- |
| Owner control centre | `/super-admin/*` | Business owner | Required + MFA before public production exposure | Operational Local Hub |
| Retail workspace | `/retail/*` | Retail admin, manager, staff, analyst | Required | Operational Local Hub |
| Cafe workspace | `/cafe/*` | Cafe admin, manager, order taker, kitchen, analyst | Required | Operational Local Hub |
| Customer table menu | `/order/:qr-token` | Cafe customer | QR-scoped guest access | Cloud Gateway |

The customer menu never renders staff navigation, owner dashboards, user management,
inventory, invoices, or administrative settings. Internal users never use the public QR
token as authentication.

## Final routing rule

### Customer

The customer path is cloud-primary in both normal and degraded operation:

```text
Customer QR browser
  -> hosted React `/order/:qr-token`
  -> restricted Cloud Gateway
  -> Supabase coordination database
  -> durable Cafe order / bill-request command
  -> Local Hub sync worker
  -> Local PostgreSQL operational workflow
```

QR resolution, published menu reads, customer order submission, customer-safe order
status, and bill-request submission use the Cloud Gateway. The customer browser never
requires direct reachability to the Local Hub.

A cloud bill request is a request/command only. It must never create an invoice, payment,
ledger entry, or stock effect in the cloud.

### Local staff

POS, waiter, kitchen, manager, inventory, billing, payment, closing, purchasing, AI tools,
and unrestricted reporting use the Operational Local Hub. On the business LAN, staff may
use the locally served PWA so operations continue when internet connectivity is lost.

### Remote owner / Super Admin

When the Local Hub is online, the Super Admin uses the hosted frontend and reaches the
Operational Local Hub through an authenticated HTTPS tunnel/private network. This is the
live source for unrestricted operational data and writes. When a read-only cloud snapshot
surface is available, it may show clearly timestamped stale/sanitized status while the Hub
is unavailable; it must not silently accept authoritative financial or stock writes.

## Backend and data authority

The full FastAPI operational backend and authoritative PostgreSQL database run on the
Local Hub device. Inventory, invoices, payments, ledgers, stock movements, daily closing,
audit history, users, purchase records, unrestricted reports, and final AI-assisted writes
remain local-authoritative.

Remote internal users reach the Local Hub API through a secure HTTPS tunnel or private
network. PostgreSQL port 5432 is never exposed to the internet.

The hosted backend remains a restricted cloud gateway. Supabase stores only approved
cloud-coordination state: sanitized Cafe menu publications, opaque QR references, durable
order intake/receipts, bill-request commands, device heartbeat and lease state,
continuity/reconciliation records, and approved dashboard snapshots. It is not a second
unrestricted operational backend.

## Expected availability

| Condition | Local staff | Remote owner/staff | Customer QR ordering |
| --- | --- | --- | --- |
| Local Hub and internet online | Full operation | Full operation through secure tunnel | Full operation through cloud |
| Internet unavailable, Local Hub online | Full local operation on LAN | Unavailable until connectivity returns | Public cloud page may be reachable only from devices with independent internet; Local Hub imports queued cloud work after reconnect |
| Local Hub unavailable, cloud healthy | Local operational workflows unavailable | Sanitized/read-only cloud status only when configured | Cloud menu and durable order/bill-request intake; final billing waits for Local Hub reconciliation |
| Both Local Hub and cloud unavailable | Offline procedures | Unavailable | Clear temporary-unavailable message |

Cloud events are reconciled into the Local Hub when it returns. Idempotency, writer leases,
receipts, dead-letter handling, and reconciliation prevent the same order or command from
being applied twice.

## Multi-device Local Hub model

One Local Hub is a server, not a single-user workstation. Multiple browsers can use the
same FastAPI/PostgreSQL authority concurrently:

```text
POS browser ---------\
Waiter phone ---------+-> Local Hub FastAPI -> Local PostgreSQL
Kitchen tablet -------+
Manager browser ------/
Remote Super Admin -- secure tunnel --/
```

Billing and stock operations must remain transactionally protected so duplicate checkout,
concurrent billing, retries, and last-stock races cannot create duplicate financial or
inventory effects.

## Deployment configuration

The frontend uses separate environment variables so customer and staff requests cannot be
accidentally routed to an inappropriate backend:

- `VITE_CLOUD_API_BASE_URL`: restricted Cloud Gateway used by the public Cafe customer route and approved continuity/read APIs.
- `VITE_OPERATIONAL_API_BASE_URL`: secure Local Hub API URL used by authenticated portals.
- `VITE_API_BASE_URL`: compatibility fallback for authenticated operational development only.

Secrets, database URLs, device credentials, and service-role keys are never placed in
frontend variables.

The Local Hub must run PostgreSQL, FastAPI, the durable sync worker, the local PWA/static
frontend, backup jobs, and the tunnel client under managed OS services with automatic
restart. Linux/systemd is the preferred dedicated-Hub profile; Windows remains supported
where peripheral compatibility requires it.

## Release acceptance

The product is ready to ship only when the following journeys pass with production-like
PostgreSQL and real browser/network execution:

1. Owner signs in with the required production authentication controls, chooses Retail or Cafe, returns to the venture selector, and views the consolidated dashboard.
2. Retail manager bills a sale and sees stock and reporting update inside the assigned branch.
3. Cafe order taker opens a table order, kitchen progresses it, and billing closes it.
4. Customer scans a QR code, resolves the cloud-published menu, places an idempotent cloud order, follows customer-safe status, and can submit a cloud bill request. Cloud code never performs final billing or stock writes.
5. The Local Hub imports cloud work exactly once and survives duplicate delivery/retry.
6. Two concurrent billing attempts for one Cafe source produce exactly one active invoice.
7. Analyst can read dashboards and export reports but cannot perform operational writes.
8. Internet interruption, Local Hub restart, and cloud recovery reconcile queues without duplicate financial or stock effects.
9. Local staff can continue POS/waiter/kitchen/billing workflows over the LAN when internet is unavailable and the Hub is healthy.
10. Backup and restore, MFA, security headers, trusted-proxy behavior, rate limits, dependency audit, and private-database checks pass before public production admin exposure.
