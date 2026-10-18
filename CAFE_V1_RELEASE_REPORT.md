# Kalpvriksh Café V1 release audit — 18 October 2026

**Audited application candidate:** `23f97a83589d658a63c9dcf8e818c494a821c4eb` on `release/cafe-v1`.

**Migration head:** `20261018_0020`. **Target tag:** `cafe-v1.0.0`, **not created**. Software acceptance passed; final production sign-off is pending physical-device checks below. This report is a documentation-only follow-up to the audited application commit.

**Blocker fixed:** the owner could not navigate to inventory. Café owner navigation now reuses the existing scoped inventory screen; cashier inventory deep links still redirect to POS. No billing engine, schema, QR/cloud/AI/Retail functionality was added or replaced.

## Gate results

| Gate | Result and evidence |
| --- | --- |
| 1. Cash | PASS: ₹200 + ₹100, immediate paid invoices. |
| 2. UPI | PASS: ₹100 with reference. |
| 3. Card | PASS: ₹300 with reference. |
| 4. Sequential customers | PASS: four distinct invoices; quantity changes, counter/takeaway and next-customer reset. |
| 5. Duplicate Pay | PASS: one UI submission per double click; explicit same-key replay leaves business rows unchanged. |
| 6. Receipt printing | Software PASS: configured name/branch, invoice/date/items/quantity/unit/line/total/payment/paid fields; 80mm CSS, receipt-only output. **Physical printer sign-off pending.** |
| 7. Reprint | PASS: repeated authorized history reprints leave invoices/payments/stock/ledger/closing rows unchanged. |
| 8. Today reconciliation | PASS: 4 orders; billed/collected ₹700; Cash ₹300, UPI ₹100, Card ₹300; outstanding ₹0; average ₹175. Owner MFA and cashier restrictions pass. |
| 9. Reports | PASS: Today, This Month, custom range and reconciled CSV; date-preset boundary regressions pass. |
| 10. Inventory | PASS: linked stock 100 → 93; owner screen and persistence after API/frontend restart verified. |
| 11. Closing | PASS: opening ₹100, expected/count ₹400, non-cash ₹400, variance ₹0. Logout leaves day open; closing survives restart and blocks new billing without effects. |
| 12. Machine reboot | **PENDING target Linux device.** Process restart and offline systemd unit validation pass; this container has no running systemd/physical host access. |
| 13. Internet disconnected | Simulation PASS: outbound browser HTTP blocked, local production billing continues without cloud configuration/workers. **Physical disconnection check pending.** |
| 14. Daily backup | Engine PASS: daily custom-format pg_dump, checksum/full-decode verification. **Actual installed timer/service firing pending target device.** |
| 15. Restore | PASS: separate disposable PostgreSQL database; every database row matches the source. |
| 16. Upgrade persistence | PASS: guarded real PostgreSQL upgrade preserves all rows; prior-revision forward migration and tagged orchestration/failure regressions pass. Systemd/package commands in tag-orchestration tests are simulated. |
| 17. Production frontend | PASS: typecheck/build, static server, SPA refresh and production CORS boundary. |
| 18. Backend regression | PASS: **306 passed, 18 optional cloud tests skipped**. Final production-browser acceptance rerun also passed after CORS/closed-day assertions. |

Additional checks: 2 frontend routing/date tests; 2 browser receipt tests including partial balances and 80-item receipts; merged systemd unit verification; shell/JavaScript syntax and Git whitespace checks. Production browser runs had no page runtime errors. All audit trading data was created only in disposable PostgreSQL test databases.

## Deployment and remaining sign-off

Follow [Linux installation](docs/CAFE_V1_LINUX.md) and [data/bootstrap/restore](docs/CAFE_PRODUCTION_DATA.md). Use `/opt/kalpvrik`, `/etc/kalpvrik/local-hub.env`, `/var/lib/kalpvrik`; enroll owner MFA and configure real menu/stock. Run `install_cafe_linux.sh prepare`, guarded new-install bootstrap (or existing-database upgrade), then `install_cafe_linux.sh activate`. PostgreSQL remains private; frontend uses its production build. Future tagged upgrades follow [CAFE_UPGRADE_GUIDE.md](CAFE_UPGRADE_GUIDE.md).

On the target Linux acceptance installation, record device/date/results for these final gates before tagging:

1. Reboot; confirm PostgreSQL/API/frontend/timer are enabled and recover without a terminal. Run `sudo -u kalpvrik bash /opt/kalpvrik/scripts/check_cafe_v1.sh` and open the desktop launcher.
2. Disconnect WAN/Wi-Fi while retaining local connectivity; complete local cashier login, a bill, next customer and logout. Print/reprint on the actual 80mm printer with browser headers/footers disabled; inspect clipping, totals and paper cut.
3. Run `sudo systemctl start kalpvrik-backup.service`; verify its successful journal/archive and active daily timer, then complete the disposable-database restore drill. Do not put test sales into a live production database.

Do not mark these gates passed or publish `cafe-v1.0.0` until device evidence is recorded. No destructive production reset or automatic restore is part of installation, testing or recovery.

## Known non-blocking limitations

- UPI/Card modes record operator-confirmed payments/references; there is no bank or terminal confirmation integration.
- Stock deduction requires the existing menu-to-product configuration; real menu/opening stock must be entered before live billing.
- Chromium/Chrome app mode is preferred; printer driver/paper settings need device setup. The business timezone is Asia/Kolkata.
- Vite reports a large-chunk warning; backend reports three upstream deprecation warnings. Optional cloud tests are outside this Café-only release.

To repeat browser acceptance, install optional `@playwright/test@1.51.1`/Chromium test tooling, build the frontend, and run against a **disposable PostgreSQL server only**:

```bash
CAFE_PRODUCTION_TEST_ADMIN_URL='postgresql+psycopg://TEST_ADMIN@127.0.0.1:5432/postgres' CAFE_RELEASE_BROWSER=1 backend/.venv/bin/python -m pytest backend/tests -q
node --test frontend/tests/cafe-v1.test.mjs
```

Ports 8000/4173 must be free. The browser test uses the actual Operational API and static production server, then restarts both, backs up/restores and verifies database preservation. Test dependencies are not production runtime requirements.
