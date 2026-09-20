# Production Operational Requirements Addendum

Status date: 2026-08-21

This addendum closes the final non-feature operational gaps identified after the release was merged to `main`. It is part of the production-readiness requirements and must be reviewed together with:

- `docs/PRODUCTION_GO_LIVE_CHECKLIST.md`
- `docs/LOCAL_HUB_LINUX_DEPLOYMENT.md`
- `docs/PROJECT_PAUSE_HANDOFF_LOCAL_HUB_NEXT.md`
- `docs/MFA_PRODUCTION_SETUP.md`

These items do not change the frozen product architecture. They are deployment, governance, reliability, and physical-operation requirements.

## 1. GitHub release governance

- [ ] Protect the `main` branch before the next development cycle.
- [ ] Require changes to reach `main` through pull requests rather than direct pushes.
- [ ] Require the unified `Release Readiness` workflow for release-bearing changes where supported by the repository plan/settings.
- [ ] Keep historical phase branches from being treated as active release sources.
- [ ] Use the current `main` release merge as the canonical source until a later reviewed release supersedes it.
- [ ] Merge or otherwise preserve the documentation-only pause handoff before development resumes.

Rationale: at the pause point, `main` was not protected. The release is verified, but future direct pushes could bypass the release gate if branch protection is not enabled.

## 2. Production monitoring and alerting

Before public operation, define real alert delivery for conditions that require operator action.

Minimum monitored conditions:

- [ ] Local Hub FastAPI unavailable.
- [ ] PostgreSQL service unavailable.
- [ ] synchronization worker unavailable.
- [ ] local frontend/PWA unavailable on the cafe LAN.
- [ ] Cafe menu publication repeatedly failing.
- [ ] backup timer/job failing.
- [ ] backup freshness exceeding the accepted recovery window.
- [ ] disk free space below an operational threshold.
- [ ] retry/dead-letter queue growing abnormally.
- [ ] cloud gateway unavailable.
- [ ] device heartbeat stale.
- [ ] writer lease/fencing unhealthy.
- [ ] tunnel/private remote-access path unavailable when remote Super Admin access is expected.

Alerts may initially be simple and low-cost, but they must reach a real operator. Monitoring that only exists as a dashboard nobody watches is not sufficient for production readiness.

## 3. Clock, timezone, and NTP

Correct system time is mandatory because invoices, daily closing, audit trails, synchronization ordering, expiry logic, and TOTP MFA depend on it.

- [ ] Set the final Local Hub timezone intentionally.
- [ ] Enable and verify NTP/system time synchronization.
- [ ] Confirm the Hub clock remains correct after reboot/power loss.
- [ ] Confirm PostgreSQL timestamps and application timestamps agree with the intended production timezone/UTC policy.
- [ ] Confirm TOTP MFA succeeds with the production clock configuration.

## 4. Production secret inventory and rotation

Generate production-only credentials during deployment. Do not reuse development, CI, preview, or demonstration secrets.

At minimum inventory and protect:

- [ ] Local Hub `SECRET_KEY`.
- [ ] Cloud Gateway `SECRET_KEY`.
- [ ] Local PostgreSQL application credential.
- [ ] Supabase runtime credential/URL.
- [ ] Supabase migration/direct credential/URL.
- [ ] `SYNC_DEVICE_SECRET` for each Local Hub.
- [ ] Cloudflare Tunnel/Tailscale credentials or equivalent remote-access credentials.
- [ ] Any future email/SMS/monitoring credentials.

Requirements:

- [ ] Secrets are not stored in git.
- [ ] Secrets are not exposed through `VITE_*` variables.
- [ ] Secrets are not copied into screenshots, tickets, chat logs, or public documentation.
- [ ] A secure offline recovery record exists for owner-controlled production credentials where appropriate.
- [ ] A rotation procedure is documented for compromised credentials.

## 5. Stable DNS and TLS naming

Avoid production dependence on changing public IP addresses or temporary preview URLs.

- [ ] Select the final hosted frontend hostname/domain.
- [ ] Select the final Cloud Gateway hostname/domain.
- [ ] Select the approved remote Local Hub operational hostname/private name.
- [ ] Use valid HTTPS/TLS for all internet-facing browser/API traffic.
- [ ] Update `FRONTEND_ORIGIN`, `FRONTEND_EXTRA_ORIGINS`, `VITE_CLOUD_API_BASE_URL`, and `VITE_OPERATIONAL_API_BASE_URL` to final approved origins/endpoints.
- [ ] Confirm no production workflow depends on a Vercel preview URL.
- [ ] Confirm LAN staff access has a stable hostname or reserved Hub LAN address.

## 6. POS peripherals and physical hardware integration

Repository tests cannot prove real printer/scanner/cash-drawer behavior. Test the exact hardware that will be deployed.

- [ ] 80 mm receipt printer prints a complete production invoice correctly.
- [ ] Printer survives service/Hub reboot without manual driver repair.
- [ ] Barcode scanner inputs correctly into the POS workflow.
- [ ] Cash drawer opens through the intended printer/interface if used.
- [ ] Kitchen printer/display behavior is verified if a physical kitchen printer is used later.
- [ ] Required Linux drivers/packages are documented.
- [ ] A replacement/spare strategy exists for the most critical POS peripheral where business continuity requires it.

## 7. Operating-system maintenance, logs, and disk capacity

The Local Hub is a 24x7 business appliance and must not fail because logs, backups, documents, or models fill the disk.

- [ ] systemd/journald/application logs have retention/rotation appropriate to the SSD capacity.
- [ ] Backup retention is configured and verified.
- [ ] Disk free space is monitored.
- [ ] A low-disk operational threshold is defined.
- [ ] Future OCR source documents/models are stored with an explicit retention policy before enabling that feature.
- [ ] OS/package update procedure is defined.
- [ ] Security updates are applied in a controlled maintenance window.
- [ ] Reboot-required updates are followed by a service/health check.
- [ ] Automatic updates must not unpredictably interrupt billing during operating hours.

## 8. Independent and off-site backup requirement

A backup on the same SSD is not a disaster-recovery backup.

- [ ] Local `pg_dump` + SHA-256 process succeeds.
- [ ] At least one backup copy is stored on media independent from the Local Hub SSD.
- [ ] At least one recoverable copy is physically or logically separated from the Hub so theft, SSD failure, corruption, or electrical damage does not destroy every copy.
- [ ] Backup retention matches the business recovery objective.
- [ ] A recent production backup is restored into a disposable PostgreSQL database.
- [ ] Restored financial totals, invoices, inventory, users, and sync state are sampled/verified.
- [ ] Replacement-Hub recovery steps are known to the operator.

## 9. Initial production data bootstrap

Before physical go-live, verify the real business data hierarchy and starting state rather than assuming demo/dev data is production-ready.

- [ ] Correct Business Group exists.
- [ ] Correct Company/Venture exists.
- [ ] Correct Branch exists.
- [ ] Final Super Admin account exists and is MFA-enrolled.
- [ ] Staff users and roles match real responsibilities.
- [ ] Cafe tables and QR tokens correspond to physical tables.
- [ ] Customer-safe menu names/descriptions/prices/availability are correct.
- [ ] Retail/Cafe product master data is reviewed.
- [ ] Opening inventory is entered/reconciled before live stock control.
- [ ] Tax/non-GST operating mode is verified for the actual business.
- [ ] Business/invoice/receipt profile details are checked before the first live invoice.
- [ ] Demo/test users/orders/invoices/stock that should not exist in production are removed through approved setup procedures.

## 10. Provider quota and deployment readiness

At the project pause point:

```text
Frontend production deployment: GREEN
Cloud API release code/preview: VERIFIED
Cloud API main production deployment: blocked by Vercel free-tier deployment quota
```

Requirements before public customer QR go-live:

- [ ] Production `cafe-retail-api` deployment for current `main` is `Ready`/green.
- [ ] Do not modify application source merely to force a Vercel redeploy when the failure is quota/rate-limit related.
- [ ] Re-check Vercel/Supabase free-tier limits before commercial/public reliance; free-tier availability must not be treated as a permanent reliability guarantee.
- [ ] Verify `/api/cloud/readiness` on the actual production Cloud Gateway after the final deployment.

## 11. Final operational acceptance

These requirements supplement, not replace, the existing physical go-live checklist.

Do not mark the system `PUBLIC PRODUCTION READY` until:

- [ ] repository release gates are green for the deployed release;
- [ ] production frontend and Cloud Gateway are green;
- [ ] Local Hub is installed and healthy;
- [ ] PostgreSQL is private;
- [ ] synchronization and Cafe publication are healthy;
- [ ] MFA is enrolled and verified;
- [ ] production secrets/DNS/TLS are finalized;
- [ ] clock/NTP is verified;
- [ ] real POS peripherals work;
- [ ] real users/data/QRs/opening stock are correct;
- [ ] monitoring/alert delivery works;
- [ ] outage/reboot recovery passes;
- [ ] independent backup/restore passes;
- [ ] every applicable item in `docs/PRODUCTION_GO_LIVE_CHECKLIST.md` is evidenced.

This addendum is intentionally operational. It should not be used as justification for redesigning the Local Hub/cloud authority boundary or starting post-release AI/OCR features before deployment is complete.
