# Production Go-Live Checklist

Use this checklist only after deploying the verified release commit. A successful build is not the same as a configured production system.

## 1. Release source

- [ ] Deploy the exact reviewed commit from `agent/release-readiness-finalization` (or its later approved merge commit).
- [ ] `Release Readiness` workflow is green for that exact commit.
- [ ] Both Local Hub and cloud migration heads match the release documentation.
- [ ] No production secret exists in git, frontend source, browser variables, logs, screenshots, or test fixtures.

Expected heads for this release:

```text
Local Hub: 20260821_0019
Cloud:     20260821_cloud_0003
```

## 2. Supabase / cloud coordination database

- [ ] Production Supabase project/database created.
- [ ] Runtime and migration URLs stored only in server-side environment settings.
- [ ] `alembic -c alembic_cloud.ini upgrade head` completed against the intended production cloud database.
- [ ] Cloud schema is coordination-only; it is not used as the authoritative invoice/payment/stock database.
- [ ] Public/customer-safe publication tables contain no cost price, password hash, unrestricted customer PII, raw QR secret, or audit payload.
- [ ] Backup/retention settings appropriate to the chosen provider have been enabled.

## 3. Hosted frontend

- [ ] Hosted frontend points `VITE_CLOUD_API_BASE_URL` to the restricted Cloud Gateway.
- [ ] Hosted frontend points `VITE_OPERATIONAL_API_BASE_URL` only to the approved HTTPS operational endpoint/tunnel.
- [ ] No service-role key or database URL exists in any `VITE_*` variable.
- [ ] `/order/:qr-token` resolves through the Cloud Gateway without direct Local Hub reachability.
- [ ] `/super-admin`, `/retail`, and `/cafe` require authentication and use the Operational Local Hub for live operational writes.

## 4. Cloud Gateway

- [ ] `DEPLOYMENT_MODE=cloud_gateway`.
- [ ] Strong unique `SECRET_KEY` configured.
- [ ] Explicit production CORS origins configured.
- [ ] API docs disabled in production unless intentionally protected.
- [ ] Cloud runtime/migration database URLs point to the cloud coordination database, never the Local Hub database.
- [ ] `GET /api/cloud/readiness` returns `status=ready` and `cloud_schema_revision=20260821_cloud_0003`.
- [ ] Public QR, menu, order, status, and bill-request endpoints are reachable.
- [ ] Local-only billing, inventory adjustment, purge, backup, unrestricted reporting, and operational admin routes are not registered in cloud-gateway mode.
- [ ] Edge/provider rate limiting is configured for login, QR resolve, order submit, bill request, heartbeat and synchronization endpoints.

## 5. Local Hub installation

Follow `docs/LOCAL_HUB_LINUX_DEPLOYMENT.md`.

- [ ] PostgreSQL installed on SSD/NVMe storage.
- [ ] Local database migrated to `20260821_0019`.
- [ ] Application installed under the approved service account/path.
- [ ] `/etc/kalpvrik/local-hub.env` is readable only by trusted root/service principals.
- [ ] API, sync worker and local frontend systemd services are enabled and active.
- [ ] Backup timer is enabled and active.
- [ ] Hub has stable LAN addressing/DHCP reservation.
- [ ] Hub is connected to the router through Ethernet where practical.
- [ ] Hub/router/ONT are protected by the planned UPS.

## 6. PostgreSQL network safety

- [ ] PostgreSQL is bound only to localhost/private interfaces required by the Hub.
- [ ] TCP 5432 is not exposed by router port forwarding, public firewall, tunnel, reverse proxy or cloud security group.
- [ ] External scan/test confirms PostgreSQL cannot be reached from the public internet.
- [ ] Only FastAPI is exposed through the approved authenticated HTTPS tunnel/private network.

## 7. Device registration and synchronization

- [ ] Local Hub has a unique device ID and revocable secret.
- [ ] Device registration scope matches the intended business group/company/branch.
- [ ] Heartbeat is accepted by the cloud coordinator.
- [ ] Writer lease/fencing epoch is healthy.
- [ ] Menu publication reaches the cloud.
- [ ] Customer cloud order imports exactly once into the Local Hub.
- [ ] Cloud bill request marks the local table session `bill_requested` without creating an invoice/payment/stock effect.
- [ ] Local status changes converge back to the customer-safe cloud order status.
- [ ] Pending/retry/dead-letter counts are visible to authorized operators.

## 8. Privileged MFA

Follow `docs/MFA_PRODUCTION_SETUP.md`.

- [ ] Final Super Admin enrolled in TOTP MFA from a trusted console/private session.
- [ ] Every publicly reachable Venture Admin enrolled in MFA.
- [ ] Recovery codes stored offline and not copied into notes/chat/logs/source control.
- [ ] Login without MFA is rejected for privileged production users.
- [ ] Correct TOTP login succeeds.
- [ ] Incorrect TOTP login fails and is audited.
- [ ] One recovery code succeeds once; replay of the same code fails.

## 9. Multi-device operational test

Run on the real cafe LAN with the intended devices.

- [ ] POS browser can login, bill and print.
- [ ] Waiter device can open/update the same Cafe workflow.
- [ ] Kitchen device sees permitted preparation work only.
- [ ] Manager/owner sees the correct scope.
- [ ] Two users acting on one table do not overwrite each other's committed state.
- [ ] Two billing attempts against the same source produce one active invoice.
- [ ] Last-stock/concurrent checkout behavior fails safely rather than overselling authoritative stock.

## 10. Customer QR acceptance

- [ ] Physical QR scans from an ordinary customer phone using mobile data.
- [ ] Menu loads from the cloud path.
- [ ] Browser price manipulation cannot change server-authoritative pricing.
- [ ] Double-tap/retry creates one cloud order reference.
- [ ] Order survives Local Hub outage and imports after recovery.
- [ ] Request Bill creates one durable request and no cloud financial record.
- [ ] Invalid/revoked QR fails closed without leaking internal data.

## 11. Remote Super Admin acceptance

- [ ] Remote owner reaches the hosted UI over HTTPS.
- [ ] Live Super Admin data comes from the Local Hub through the approved tunnel/private network.
- [ ] Venture isolation remains enforced by the backend.
- [ ] When Local Hub is unreachable, the UI does not silently perform financial or stock writes in cloud mode.
- [ ] Any cloud snapshot shown while offline is clearly timestamped/stale-labelled and read-only.

## 12. Internet and power failure tests

- [ ] Disconnect internet while keeping LAN/router powered: local POS/waiter/kitchen/billing continue.
- [ ] Restore internet: Local Hub automatically reconnects and queues drain.
- [ ] Stop/reboot Local Hub while customer cloud ordering remains available: cloud order stays durable.
- [ ] Restart Hub: systemd services start without interactive login and cloud work imports from persisted checkpoints.
- [ ] Repeat/duplicate delivery produces no duplicate order, invoice, payment, ledger or stock movement.
- [ ] UPS behavior and controlled shutdown/recovery have been tested.

## 13. Backup and restore

- [ ] Scheduled `pg_dump` backup completes successfully.
- [ ] SHA-256 sidecar verifies.
- [ ] Backup is copied to storage independent of the Hub internal SSD.
- [ ] A recent backup has been restored into a disposable PostgreSQL database.
- [ ] Restored database contains the expected Alembic head, users, invoices, inventory and synchronization queue/checkpoint tables.
- [ ] Operator knows the recovery procedure for replacing the Local Hub device.

## 14. Dependency and browser gate

- [ ] Python dependency audit has no unaccepted high/critical finding.
- [ ] Production npm dependency audit has no unaccepted high/critical finding.
- [ ] Backend full regression passes.
- [ ] Frontend TypeScript/build passes.
- [ ] Browser release smoke passes in Chromium.
- [ ] Security-header and production-config tests pass.

## 15. Go-live decision

Only mark the system **PUBLIC PRODUCTION READY** after all applicable boxes above are evidenced for the exact release commit and physical/provider environment.

If a box depends on a real provider, network, printer, UPS or physical Local Hub, repository CI cannot prove it. Record the evidence during deployment rather than converting the item to an assumed pass.
