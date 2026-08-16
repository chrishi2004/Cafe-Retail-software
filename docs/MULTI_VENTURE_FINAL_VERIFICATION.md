# Multi-Venture Final Verification

Status: P11 security and release verification in progress. This document records evidence without claiming production readiness.

## Release gate

| Area | Evidence | Status |
| --- | --- | --- |
| Cross-venture authorization | P2 suite and later phase workflows | Pass when the P11 workflow is green |
| Token expiry, logout, and token-version revocation | Existing auth tests plus P11 security tests | Pass when the P11 workflow is green |
| Explicit CORS and production docs protection | Settings.cors_origins, resolved_api_docs_enabled, P11 tests | Pass when the P11 workflow is green |
| Security headers and auth throttling | security_hardening.py, P11 tests | Pass when the P11 workflow is green |
| Cafe QR/order/billing flow | P1-P9 verification and P11 regression workflow | Pass when the P11 workflow is green |
| Closing, void, purge, and audit evidence | P10 report and P11 regression workflow | Pass when the P11 workflow is green |
| PostgreSQL migration/recovery | Existing HC workflows; P11 workflow records available commands | Pending environment evidence |
| Browser E2E and viewport coverage | Existing frontend build; browser execution required before release | Pending |
| Backup/restore drill | Existing backup guide; disposable restore execution required before release | Pending |
| MFA/TOTP for Super Admin and Venture Admin | No MFA secret/challenge model exists in the P10 baseline | Gap — release blocker for public production access |

## MV-FR mapping

- MV-FR-001 to MV-FR-006: venture hierarchy, roles, scope isolation — P1/P2 reports and cross-venture tests.
- MV-FR-007 to MV-FR-012: Cafe QR sessions, safe menu, guest ordering, idempotency — P3/P4 reports and public Cafe tests.
- MV-FR-013 to MV-FR-018: staff queue, preparation, billing, payment, receipt — P5/P6 reports and Cafe workflow tests.
- MV-FR-019 to MV-FR-024: Cafe and consolidated dashboards, exports, AI scope — P9 report and P9 tests.
- MV-FR-025 to MV-FR-030: closing, reversal, purge approvals, immutable audit evidence — P10 report and P10 tests.
- MV-FR-031 to MV-FR-036: hybrid continuity, durable queue, leases, recovery controls — HC1-HC4 reports and workflows.
- MV-FR-037 to MV-FR-042: release hardening, documentation, QA, backup/restore — P11 workflow, report, and manual evidence.

## Release recommendation

Not ready for public production until MFA/TOTP, PostgreSQL migration evidence, browser E2E, and backup/restore drill are completed. Local/demo operation may proceed with explicit credentials, private PostgreSQL, and no public admin exposure.
