# Final Product Operating Model

This document is the product boundary for the Kalpvrik Retail and Cafe suite.
It keeps the user experiences separate while reusing one repository, one design
system, and one set of verified business rules.

## User-facing applications

The frontend is one low-cost Vercel deployment with three isolated route
surfaces. They may later receive separate custom domains without splitting the
codebase.

| Surface | Route | Audience | Authentication | API target |
| --- | --- | --- | --- | --- |
| Owner control centre | `/super-admin/*` | Business owner | Required | Operational Local Hub |
| Retail workspace | `/retail/*` | Retail admin, manager, staff, analyst | Required | Operational Local Hub |
| Cafe workspace | `/cafe/*` | Cafe admin, manager, order taker, kitchen, analyst | Required | Operational Local Hub |
| Customer table menu | `/order/:qr-token` | Cafe customer | QR-scoped guest access | Operational API first; automatic cloud continuity fallback |

The customer menu never renders staff navigation, owner dashboards, user
management, inventory, invoices, or administrative settings. Internal users
never use the public QR token as authentication.

## Backend and data authority

The full FastAPI operational backend and authoritative PostgreSQL database run
on the Local Hub device. Inventory, invoices, payments, ledgers, stock
movements, daily closing, audit history, users, and unrestricted reports remain
local-authoritative.

Remote internal users reach the Local Hub API through a secure HTTPS tunnel or
private network. PostgreSQL port 5432 is never exposed to the internet.

The Vercel backend remains a restricted cloud gateway. Supabase stores only the
approved cloud-coordination state: sanitized Cafe menu publications, opaque QR
references, order intake/receipts, device heartbeat and lease state,
continuity/reconciliation records, and approved dashboard snapshots. It is not
a second unrestricted operational backend.

## Expected availability

| Condition | Local staff | Remote owner/staff | Customer QR ordering |
| --- | --- | --- | --- |
| Local Hub and internet online | Full operation | Full operation through secure tunnel | Full operation |
| Internet unavailable, Local Hub online | Full local operation | Unavailable until connectivity returns | Local-network ordering only |
| Local Hub unavailable, cloud continuity healthy | Unavailable | Sanitized cloud status only | Cloud menu and order intake; billing waits for Local Hub reconciliation |
| Both Local Hub and cloud unavailable | Offline procedures | Unavailable | Clear temporary-unavailable message |

Cloud events are reconciled into the Local Hub when it returns. Idempotency,
writer leases, receipts, dead-letter handling, and reconciliation prevent the
same order from being applied twice.

## Deployment configuration

The frontend uses separate environment variables so a customer request is not
accidentally sent to an internal-only or restricted endpoint:

- `VITE_OPERATIONAL_API_BASE_URL`: secure Local Hub API URL used by authenticated portals and direct public ordering while the hub is reachable.
- `VITE_CLOUD_API_BASE_URL`: restricted Vercel cloud gateway used for approved continuity routes.
- `VITE_API_BASE_URL`: compatibility fallback for the authenticated operational client.

Secrets, database URLs, device credentials, and service-role keys are never
placed in frontend variables.

## Release acceptance

The product is ready to ship only when the following persona journeys pass in
a real browser:

1. Owner signs in, chooses Retail or Cafe, returns to the venture selector, and views the consolidated dashboard.
2. Retail manager bills a sale and sees stock and reporting update inside the assigned branch.
3. Cafe order taker opens a table order, kitchen progresses it, and billing closes it.
4. Customer scans a QR code, sees only the menu, places an idempotent order, follows status, and requests the bill.
   If the Local Hub is unavailable, the same QR page visibly enters cloud continuity; it never performs cloud billing or stock writes.
5. Analyst can read dashboards and export reports but cannot perform operational writes.
6. Local Hub interruption and recovery reconcile cloud events without duplicate financial or stock effects.
7. Backup and restore, MFA, security headers, rate limits, and private-database checks pass.
