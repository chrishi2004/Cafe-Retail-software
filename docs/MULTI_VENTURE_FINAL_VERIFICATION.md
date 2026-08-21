# Multi-Venture Final Verification

Status: P11 implementation is complete; release-remediation work is implemented on `agent/release-readiness-finalization`. Public production still requires green automated release evidence plus real provider/Local Hub deployment evidence.

## Release gate

| Area | Evidence | Current status |
| --- | --- | --- |
| Cross-venture authorization | P2 suite and later regression suites | Implemented; must remain green in Release Readiness CI |
| Token expiry, logout, token-version revocation | Existing auth tests plus P11 security tests | Implemented; must remain green in Release Readiness CI |
| Explicit CORS and production docs protection | Settings + P11 tests | Implemented; deployment values still require environment verification |
| Security headers and auth throttling | `security_hardening.py`, P11 tests | Implemented; edge/provider rate limits still require provider configuration |
| Cafe QR/order/billing flow | P1-P9/HC3 plus release remediation | Implemented; hosted customer route is now cloud-primary |
| Cloud bill request | Independent cloud bill-request aggregate + Local Hub handler | Implemented; creates no cloud financial/stock effect |
| Closing, void, purge, audit | P10 report/regression | Implemented |
| PostgreSQL migration/recovery | HC workflows + Release Readiness migrations | Automated gate added; production database evidence still required |
| Browser E2E | Headless Chromium release smoke | Implemented in Release Readiness CI; real-device acceptance still required |
| Backup/restore drill | Verified dump/checksum/disposable restore in Release Readiness CI | Automated gate added; physical independent-backup restore still required |
| MFA/TOTP for Super Admin and Venture Admin | Encrypted TOTP secret, hashed recovery codes, login/step-up enforcement, console bootstrap, tests | Implemented; production privileged accounts must actually be enrolled before public exposure |
| Linux Local Hub services | systemd API/sync/frontend/backup + health check | Implemented in repository; physical-host boot/network evidence required |
| Dependency audits | `pip-audit` + production `npm audit` in Release Readiness workflow | Automated gate added; findings must be resolved/accepted before go-live |

## MV-FR mapping

- MV-FR-001 to MV-FR-006: venture hierarchy, roles, scope isolation — P1/P2 reports and cross-venture tests.
- MV-FR-007 to MV-FR-012: Cafe QR sessions, safe menu, guest ordering, idempotency — P3/P4 plus cloud-primary release remediation.
- MV-FR-013 to MV-FR-018: staff queue, preparation, billing, payment, receipt — P5/P6/P8 plus cloud bill-request remediation.
- MV-FR-019 to MV-FR-024: Cafe and consolidated dashboards, exports, AI scope — P9 report and tests.
- MV-FR-025 to MV-FR-030: closing, reversal, purge approvals, immutable audit evidence — P10 report and tests.
- MV-FR-031 to MV-FR-036: hybrid continuity, durable queue, leases, recovery controls — HC1-HC4 plus independent bill-request aggregate.
- MV-FR-037 to MV-FR-042: release hardening, documentation, QA, backup/restore — P11 plus Release Readiness workflow/runbooks.

## Release migration heads

```text
Local Hub: 20260821_0019
Cloud:     20260821_cloud_0003
```

## Release recommendation

Repository-side release remediation is implemented. Do not call the deployed system `PUBLIC PRODUCTION READY` until:

1. `.github/workflows/release-readiness.yml` is green for the exact deployment commit;
2. production Local Hub and cloud migrations are applied to the intended databases;
3. production Super Admin/Venture Admin accounts are enrolled in MFA;
4. PostgreSQL public-network isolation is evidenced;
5. the approved HTTPS tunnel/private-network path is evidenced;
6. real POS/waiter/kitchen/customer QR/remote Super Admin journeys pass on the intended devices;
7. internet loss, Hub reboot, queue recovery and physical backup/restore are exercised;
8. provider/edge rate limiting and any remaining dependency findings are resolved.

Use `docs/PRODUCTION_GO_LIVE_CHECKLIST.md` as the deployment evidence record.
