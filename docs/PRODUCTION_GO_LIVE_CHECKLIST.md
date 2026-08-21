# Production Go-Live Checklist

Use this checklist only after deploying the verified release commit. A successful build is not the same as a configured production system.

## 1. Release source

- [ ] Deploy the exact reviewed commit from `agent/release-readiness-finalization` or its approved merge commit.
- [ ] `Release Readiness` is green for that exact commit/PR.
- [ ] Local Hub and cloud migration heads match this release.
- [ ] No production secret exists in git, frontend/browser variables, logs, screenshots or test fixtures.

Expected heads:

```text
Local Hub: 20260821_0019
Cloud:     20260821_cloud_0003
```

## 2. Supabase / cloud coordination database

- [ ] Production Supabase project/database exists.
- [ ] Runtime/migration URLs are stored only in protected server-side configuration.
- [ ] `alembic -c alembic_cloud.ini upgrade head` completed against the intended cloud database.
- [ ] Cloud schema is coordination-only, never authoritative invoice/payment/stock storage.
- [ ] Customer-safe publication tables contain no cost price, password hash, unrestricted customer PII, raw QR proof or audit payload.
- [ ] Provider backup/retention settings appropriate to the deployment are enabled.

## 3. Hosted frontend

- [ ] `VITE_CLOUD_API_BASE_URL` points to the restricted Cloud Gateway.
- [ ] `VITE_OPERATIONAL_API_BASE_URL` points only to the approved HTTPS operational tunnel/private endpoint.
- [ ] No service-role key/database URL/device secret exists in any `VITE_*` variable.
- [ ] `/order/:qr-token` resolves through cloud without direct Local Hub reachability.
- [ ] `/super-admin`, `/retail` and `/cafe` require authentication and use Local Hub for operational writes.

## 4. Cloud Gateway

- [ ] `DEPLOYMENT_MODE=cloud_gateway`.
- [ ] Strong unique `SECRET_KEY` configured.
- [ ] `FRONTEND_ORIGIN` / `FRONTEND_EXTRA_ORIGINS` explicitly list approved origins.
- [ ] API docs disabled in production unless intentionally protected.
- [ ] Cloud database URLs point to coordination DB, never Local Hub DB.
- [ ] `GET /api/cloud/readiness` returns `status=ready` and `cloud_schema_revision=20260821_cloud_0003`.
- [ ] Public QR/menu/order/status/bill-request endpoints are reachable.
- [ ] Local-only billing/inventory/purge/backup/unrestricted reporting/admin write routes are absent in cloud-gateway mode.
- [ ] Edge/provider rate limiting is configured for public and synchronization endpoints.

## 5. Local Hub installation

Follow `docs/LOCAL_HUB_LINUX_DEPLOYMENT.md`.

- [ ] PostgreSQL installed on SSD/NVMe.
- [ ] Local database migrated to `20260821_0019`.
- [ ] Application installed under approved service account/path.
- [ ] `/etc/kalpvrik/local-hub.env` has restricted permissions.
- [ ] API, sync worker and local frontend services enabled/active.
- [ ] Backup timer enabled/active.
- [ ] Cafe menu publication timer enabled/active.
- [ ] Stable LAN addressing/DHCP reservation configured.
- [ ] Ethernet used for Hub-to-router where practical.
- [ ] Hub/router/ONT protected by planned UPS.

## 6. PostgreSQL network safety

- [ ] PostgreSQL bound only to localhost/private interfaces required by the Hub.
- [ ] TCP 5432 is not exposed by router port forwarding, public firewall, tunnel, reverse proxy or cloud security group.
- [ ] External scan/test confirms PostgreSQL cannot be reached from the public internet.
- [ ] Only FastAPI is exposed through the approved authenticated HTTPS tunnel/private network.

## 7. Device registration and synchronization

- [ ] Strong unique `SYNC_DEVICE_SECRET` generated and stored only on the Local Hub.
- [ ] Trusted registration succeeds:

```bash
cd /opt/kalpvrik/backend
set -a; source /etc/kalpvrik/local-hub.env; set +a
export CLOUD_MIGRATION_DATABASE_URL='postgresql+psycopg://<protected-direct-supabase-url>'
.venv/bin/python -m scripts.register_cloud_device
```

- [ ] Registration scope matches the intended business group/company/branch.
- [ ] Cloud stores only the device credential hash, not the raw secret.
- [ ] Heartbeat accepted by cloud coordinator.
- [ ] Writer lease/fencing healthy.
- [ ] Initial Cafe cloud snapshot succeeds:

```bash
.venv/bin/python -m scripts.publish_cafe_menu --force
```

- [ ] `kalpvrik-menu-publish.timer` subsequently skips unchanged data and republishes changed customer-safe menu/QR/availability state.
- [ ] Customer cloud order imports exactly once into Local Hub.
- [ ] Cloud bill request marks local table `bill_requested` without cloud invoice/payment/stock effect.
- [ ] Local status changes converge to customer-safe cloud status.
- [ ] Pending/retry/dead-letter counts are visible to authorized operators.

## 8. Privileged MFA

Follow `docs/MFA_PRODUCTION_SETUP.md`.

- [ ] Final Super Admin enrolled in TOTP MFA from trusted console/private session.
- [ ] Every publicly reachable Venture Admin enrolled in MFA.
- [ ] Recovery codes stored offline, not copied to source/chat/logs.
- [ ] Privileged production login without MFA is rejected.
- [ ] Correct TOTP succeeds; incorrect TOTP fails and is audited.
- [ ] One recovery code succeeds once; replay fails.

## 9. Multi-device operational test

Run on the actual cafe LAN.

- [ ] POS can login, bill and print.
- [ ] Waiter device can operate the same Cafe workflow within role scope.
- [ ] Kitchen device sees permitted preparation work only.
- [ ] Manager/owner sees correct venture/branch scope.
- [ ] Two users acting on one table do not overwrite committed state.
- [ ] Two billing attempts against same source produce one active invoice.
- [ ] Last-stock concurrent checkout fails safely rather than overselling authoritative stock.

## 10. Customer QR acceptance

- [ ] Physical QR scans from an ordinary phone using mobile data.
- [ ] Menu loads through the hosted/cloud path.
- [ ] Browser price manipulation cannot change server-authoritative pricing.
- [ ] Double-tap/retry creates one cloud order reference.
- [ ] Order survives Local Hub outage and imports after recovery.
- [ ] Request Bill creates one durable request and no cloud financial record.
- [ ] Invalid/revoked QR fails closed without leaking internal data.
- [ ] A menu/availability change on Local Hub is reflected after the publication timer runs.

## 11. Remote Super Admin acceptance

- [ ] Remote owner reaches hosted UI over HTTPS.
- [ ] Live Super Admin data comes from Local Hub through approved tunnel/private network.
- [ ] Venture isolation remains backend-enforced.
- [ ] When Local Hub is unreachable, UI does not silently perform financial/stock writes in cloud mode.
- [ ] Any cloud snapshot displayed offline is timestamped/stale-labelled/read-only.

## 12. Internet and power failure tests

- [ ] Disconnect internet while keeping LAN/router powered: local POS/waiter/kitchen/billing continue.
- [ ] Restore internet: Local Hub reconnects automatically and queues drain.
- [ ] Stop/reboot Local Hub while customer cloud ordering remains available: cloud order stays durable.
- [ ] Restart Hub: systemd services/timers start without interactive login and cloud work imports from persisted checkpoints.
- [ ] Duplicate delivery creates no duplicate order/invoice/payment/ledger/stock movement.
- [ ] UPS behavior and controlled shutdown/recovery tested.

## 13. Backup and restore

- [ ] Scheduled `pg_dump` completes.
- [ ] SHA-256 sidecar verifies.
- [ ] Backup copied to storage independent of Hub SSD.
- [ ] Recent backup restored into disposable PostgreSQL DB.
- [ ] Restored DB has expected Alembic head, users, invoices, inventory, sync queues/checkpoints.
- [ ] Operator knows replacement-Hub recovery procedure.

## 14. Dependency and browser gate

- [ ] Python dependency audit has no unaccepted high/critical finding.
- [ ] Production npm dependency audit has no unaccepted high/critical finding.
- [ ] Full backend regression passes.
- [ ] Frontend TypeScript/build passes.
- [ ] Chromium release smoke passes.
- [ ] Security-header/production-config tests pass.
- [ ] Cloud gateway URL normalization test passes for both host-root and `/api` configurations.

## 15. Go-live decision

Only mark **PUBLIC PRODUCTION READY** after every applicable item above is evidenced for the exact release commit and physical/provider environment.

Items requiring a real provider, network, printer, UPS or physical Local Hub cannot be proven by repository CI. Record real evidence during deployment instead of converting those items to assumed passes.
