# HC2 Cloud Coordination Boundary

## Purpose

HC2 introduces the minimal cloud coordination layer required before customer ordering can be implemented. Local PostgreSQL remains authoritative for inventory, invoices, payments, ledgers, stock movements, closing, and complete operational audit history.

## Runtime Profiles

### Local Hub

The Local Hub retains the complete operational API and local PostgreSQL. It builds sanitized, versioned Cafe publications from authoritative menu, table, QR-verifier, and inventory-availability state.

### Cloud Gateway

The cloud gateway registers only:

- `/api/health`
- `/api/cloud/readiness`
- `/api/cloud/devices/heartbeat`
- `/api/cloud/publications/menu`
- `/api/cloud/public/cafe/menu/{publication_id}`
- `/api/cloud/public/cafe/qr/resolve`

It does not register Local Hub authentication, inventory adjustment, invoice issue, payment, purchase receiving, AI, backup, or unrestricted reporting routes.

Customer ordering remains disabled in HC2.

## Cloud Database

Cloud coordination uses a separate Alembic history and a dedicated `coordination` PostgreSQL schema.

The first cloud revision is:

`20260813_cloud_0001`

The schema contains coordination foundations for device state, heartbeats, writer leases, versioned Cafe publications, table verifier digests, cloud order scaffolding, idempotency, synchronization commands/receipts, dashboard and availability snapshots, continuity records, and tombstones.

Row-level security is enabled on every coordination relation. HC2 does not add direct browser database access or browser database credentials. The Vercel backend is the access boundary.

## Publication Contract

A Cafe publication carries:

- business-group, company, and branch scope for backend validation;
- a globally unique publication ID;
- monotonically supplied publication version;
- snapshot timestamp;
- customer-safe category and menu fields;
- customer selling prices;
- preparation area and menu availability;
- active table display identity;
- table public reference plus one-way verifier digest;
- boolean product availability only.

It does not carry cost prices, authoritative stock quantities, user records, customer ledgers, unrestricted audit payloads, or recoverable table credentials.

Publication is atomic:

1. create the version as `staging`;
2. insert categories, items, table verifier records, and availability snapshots;
3. supersede the previous active version;
4. activate the new version in the same transaction;
5. commit.

A staging or failed publication is never returned by public menu resolution. Replaying the same publication ID and same content returns the original result. Reusing that ID with changed content is rejected.

## Device Boundary

Heartbeat and publication calls require a pre-provisioned active device registration that is scoped to allowed purposes and business scope. Disabled or revoked registrations fail closed. Device provisioning is an administrative operation in HC2; there is no anonymous device-registration endpoint.

## Freshness

Public cloud responses include `snapshot_at` and `stale_age_seconds`. The frontend contains a cloud-safe client and freshness display component. Customer ordering remains explicitly disabled until P6.

## Configuration

Server-side cloud deployment uses:

- `DEPLOYMENT_MODE=cloud_gateway`
- `CLOUD_RUNTIME_DATABASE_URL` for Vercel runtime traffic through the supported serverless transaction pooler
- `CLOUD_MIGRATION_DATABASE_URL` for Alembic/admin migration traffic
- `HEARTBEAT_INTERVAL_SECONDS`
- `WRITER_LEASE_SECONDS`

Local publication transport additionally uses the configured gateway URL and the Local Hub device identity managed by HC1 configuration.

Browser configuration may use:

- `VITE_CLOUD_API_BASE_URL`
- `VITE_OPERATIONAL_API_BASE_URL`

Server database, migration, and device configuration must never be placed in browser variables.

## HC2 Boundary

HC2 intentionally does not implement:

- public customer order submission;
- cloud financial writing;
- authoritative cloud stock changes;
- emergency payment processing;
- full HC3 bidirectional synchronization;
- P6 guest session/order lifecycle.

Those remain closed until their later phase gates.
