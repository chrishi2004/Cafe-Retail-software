# Kalpvriksh Full V2 — F0 production upgrade baseline

Audit date: 2026-10-18. **F0 acceptance BLOCKED; development tooling implemented, customer deployment prohibited.** This is not a V1 or V2 production release certificate. Do not advance to F1 until the pending gates below pass.

## 1. Exact source and installed baseline

| Evidence | Result |
| --- | --- |
| Remote main | `d9cffb00d24605ba8059d00cede5c56a0b753cf2` |
| Latest remote Café V1 | `9ab1eb67cea5d6cb613a582455cc53099834cacc` |
| Application candidate recorded in C6 report | `23f97a83589d658a63c9dcf8e818c494a821c4eb` |
| Candidate → latest V1 | Documentation-only: README and CAFE_V1_RELEASE_REPORT.md |
| Main → latest V1 | 0 commits behind, 7 ahead |
| `cafe-v1.0.0` / published GitHub releases | Absent at audit; no tag fabricated |
| Installed customer version, source cleanliness, schema | **UNKNOWN: no customer-machine access** |
| Development checkout before branching | Clean; no local-only/unpushed commits |
| Development branch base | `release/full-v2` created directly at latest V1 SHA above; no merge/rebase |
| Local migration head | `20261018_0020` |
| Independent cloud migration head | `20260821_cloud_0003` |

The branch is permitted for F0 preparation only. It is not evidence that V1 was deployed or physically accepted. Keep the customer's current installation unchanged. The previous Mac test discussion does not establish the running revision, scheduled backups, Linux reboot acceptance or production data reconciliation.

Executed read-only source inspection:

```bash
git status --short --branch
git log --branches --not --remotes --oneline
git fetch origin
git ls-remote --tags origin
git rev-parse origin/main origin/release/cafe-v1
git rev-list --left-right --count origin/main...origin/release/cafe-v1
```

After those checks, the only branch operation was:

```bash
git switch -c release/full-v2 9ab1eb67cea5d6cb613a582455cc53099834cacc
```

On the actual installed machine, collect `git status --short --branch`, `git log --branches --not --remotes --oneline`, `git rev-parse HEAD`, `git describe --tags --exact-match HEAD`, configured environment-file path, service definitions and `cafe_production.py status`. Do not print secrets or copy the environment file into Git. A failed exact-tag lookup is evidence of an untagged installation, not permission to create a tag. Preserve any local edits in place and review them before cutover. Do not run preparation/build/checkout inside the live code directory during F0.

## 2. Existing structures and services to reuse

| Area | Actual structures / scope |
| --- | --- |
| Group | `business_groups`: legal identity, currency, active state |
| Venture | `companies.business_group_id`, `business_type` (`cafe`/`retail`), group-unique slug; company code and name globally unique |
| Branch | `branches.company_id`; branch name unique within company |
| Users | Group/company/branch scope, globally unique email, role, password hash, token version, MFA material; super-admin has no company/branch; other roles require company |
| Café menu | `menu_categories`, `menu_items`: company, optional branch, stable public IDs; optional product link |
| Orders | `cafe_orders`, `cafe_order_items`, `table_sessions`, tables/tokens; existing order state machine and local/cloud references |
| Financial history | `invoices`, items, taxes, payments, status history; invoice source links and company-scoped billing idempotency uniqueness |
| Numbering | `invoice_sequences`: company/optional branch/type/fiscal year, prefix, next number, padding/reset rule; never reset existing sequences |
| Tax/branding | `business_profiles`, `gst_registrations`, global `tax_rates`, company-scoped payment modes and print templates |
| Stock | Company-scoped products, branch/product inventory balances, stock movements, suppliers and purchases |
| Customers | Company/optional branch customers, addresses, payments and ledger entries |
| Closing/governance | `business_day_closures` unique company/branch/date, cash/non-cash/variance; reversals, purge requests and audit history |
| Reports | Existing P9 dashboard/consolidation and CSV services; date range and Asia/Kolkata business-day calculations |
| Production | Singleton `production_installations` marker; guarded bootstrap/upgrade/restore and external configuration |

P1–P11, P9/P10, HC0–HC4 and R5–R9 implementations and reports were inspected. Reuse `cafe_pos`, `cafe_order_engine`, `cafe_billing`, inventory/invoice services, `p9_reporting`, governance, scope enforcement, MFA and existing sync/outbox/inbox. Historical phase reports are not proof of current acceptance. The Operational API owns financial writes; the independent Cloud Gateway schema is coordination only. No second operational financial database or billing engine is introduced.

**Installed record audit is pending.** No actual customer users, customers, menu rows, invoices, payments, stock, closures or reports were supplied or queried. Do not substitute fixture counts for installed business totals.

## 3. Source preservation contract

`docs/baselines/cafe-v1-source.json` freezes SHA-256 hashes of 396 V1 source, migration, test, deployment and dependency files at the exact base commit. It contains no business data or secrets. Git history anchors its contents; never regenerate it to conceal a regression.

```bash
python scripts/check_cafe_v1_baseline.py
git merge-base --is-ancestor 9ab1eb67cea5d6cb613a582455cc53099834cacc HEAD
git diff --name-status --find-renames 9ab1eb67cea5d6cb613a582455cc53099834cacc HEAD
```

The check verifies every manifest hash against the original Git object, checks complete coverage and ancestry, blocks missing/renamed original files, and lists changed original files for explicit review. It does not prove that routes/functions inside an edited file remain compatible: review every listed file and rerun regression/browser acceptance. Unexpected route, component, service, schema or field removal blocks release even if a file still exists. Reviewed replacements need a separately reviewed preservation policy; never silently waive them.

F0 adds files only. No existing Café route/component/service/model, deployment script, migration or runtime setting is edited. No shared Café behavior change requires justification in this phase.

## 4. Non-destructive Retail addition design

1. Resolve the existing Café company by verified ID, type and group; never assume group/company/branch ID 1. Stop for ambiguous or inconsistent scope relationships.
2. Within that same BusinessGroup and same Local Hub PostgreSQL database, add a **new** Retail Company with unique code/name/slug, then its Branch, business profile, legally approved tax configuration, payment modes, print templates and independent invoice sequences. Preserve all Café IDs, foreign keys, invoice snapshots, tax settings, prefixes and counters.
3. Create separately scoped Retail employees through existing user services. Globally unique user emails require distinct employee logins. Do not broaden Café staff scope or change their roles. Preserve MFA and external encryption keys. Consolidated owner access uses existing authorized group scope, not cashier privilege expansion.
4. Configure real Retail catalog/opening stock as an audited operation later; do not seed demo transactions or manufacture historical balances. No cross-company product sharing or stock transfer by direct foreign-key reassignment.
5. Existing schema already represents both venture types. **No F0 migration is required.** Later verified gaps must use additive Alembic revisions after `20261018_0020`; preserve cloud migration independence. No reseed, `create_all`, `stamp`, destructive downgrade or database replacement during normal upgrades.

## 5. Backup, restore and staging reconciliation runbook

Status: **NOT EXECUTED against customer data or PostgreSQL here.** This environment has no PostgreSQL client/server tools. Archive verification, successful disposable restore and source report reconciliation remain mandatory evidence, not inferred passes.

Use existing production backup tooling on the installed V1 machine, with its existing external configuration. Do not install V2 there. Record current pg_dump/pg_restore/server versions and a successful backup job. Take the cutover backup with all writers quiesced; an online F0 inspection backup may run without stopping sales, but source snapshots at different times will differ legitimately.

```bash
# Existing installed V1 maintenance only; no source checkout or migration.
cd /opt/kalpvrik
KALPVRIK_ENV_FILE=/etc/kalpvrik/local-hub.env bash scripts/pre_upgrade_backup.sh
# Record the returned archive path, checksum/JSON metadata, UTC time and source identity.
KALPVRIK_ENV_FILE=/etc/kalpvrik/local-hub.env backend/.venv/bin/python \
  backend/scripts/cafe_production.py verify-backup --archive "$ARCHIVE"
```

Run as the existing authorized maintenance account with backup-directory permissions. `$ARCHIVE` is the exact returned path. Backups remain under `/var/lib/kalpvrik/backups/postgres`, outside Git/code. Preserve archive, `.sha256` and `.json` together. Existing code enforces custom-format archive, checksum, TOC and full decompression plus at least 30-day retention. Make a verified copy on a separately controlled device/location; an archive on the same disk is not an independent copy. No independent-copy automation or device verification is certified by F0.

On an **isolated staging host/cluster**, create a new empty `cafe_restore_f0_*` database through its administrator. Copy the verified bundle and existing V1 external configuration into protected staging storage; replace all database endpoints, origins and ports. Use a separate PostgreSQL cluster/port (e.g. 55432), API 18000 and UI 14173 for manual staging. Do not run systemd installers, schedulers or workers from staging. Keep staged sync/cloud credentials disabled; copied users/MFA secrets and customer data need restricted access and no public exposure. The existing automated browser test uses 8000/4173 and therefore belongs only on an isolated CI/test host where those ports are free, never beside the live V1 instance.

Set `KALPVRIK_ENV_FILE` to the **staging** external file and `KALPVRIK_DATA_DIR` to a staging data directory outside the repository. Configure `CAFE_RESTORE_DATABASE_URL` privately for that empty target; URLs/passwords must not be committed or passed as CLI arguments. Use the existing restore script:

```bash
bash scripts/restore_postgres.sh --archive "$ARCHIVE" \
  --target-env CAFE_RESTORE_DATABASE_URL --confirm-database "$RESTORE_DB_NAME"
```

Verify the archive metadata against the recorded source identity; the restore target must differ from both the configured database and archived source database. The wrapper permits only empty `cafe_restore_*` targets, refuses same-source names, and never uses `--clean`. Do not execute this command with a live target. For the restore command, the staging configuration must point to a separate staging control database, not the restore target or live database. Restore contacts only the explicit target. For the subsequent guarded upgrade, use a separate staging configuration pointing to the restored copy, and unset any backup URL targeting the control database. No staging configuration needs live production connectivity.

Before any staging writes, capture a frozen baseline, migrate the disposable copy, and capture again:

```bash
# F0_STAGING_DATABASE_URL comes from a private staging configuration.
# It must not equal LOCAL_DATABASE_URL/DATABASE_URL/LOCAL_BACKUP_DATABASE_URL.
export F0_STAGING_ACK=isolated-not-live
python backend/scripts/full_v2_baseline.py capture --output "$EVIDENCE/v1-before.json"
# Existing guarded upgrade, configured to target ONLY the disposable staging copy:
python backend/scripts/cafe_production.py upgrade
python backend/scripts/full_v2_baseline.py capture --output "$EVIDENCE/v2-after.json"
python backend/scripts/full_v2_baseline.py compare \
  --before "$EVIDENCE/v1-before.json" --after "$EVIDENCE/v2-after.json"
```

Use the staging virtual environment's Python. `$EVIDENCE` is a new restricted directory outside Git. Capture refuses overwriting an existing file and writes mode 0600 on POSIX. Read-only REPEATABLE READ captures canonical row counts/hashes for **every public table** except Alembic's version table, plus existing column definitions, reporting-view definition hashes, serial-sequence state and invoice/tax/payment/stock/closing rollups. Historical changes/removals fail comparison; additive tables are listed; revision changes are reported but are **not** proof of a valid migration path. Missing permissions/schema fail closed. Compare does not accept arbitrary historical backfills: later migrations that change historical rows require a reviewed, explicit reconciliation contract. Freeze all staging writers: sequence state is not MVCC-consistent. Do not run login tests until after comparison, because logins legitimately update user/audit rows.

The supplied test `test_populated_v1_backup_restore_forward_migration_reconciles` uses V1-pinned Alembic revision `20261018_0020`, existing configuration helpers and checkout **only in newly created disposable fixture databases**. It creates three payment-mode transactions, tests replay, snapshots populated history, verifies backup, restores, runs the existing guarded forward upgrade and compares all historical tables/sequences, inventory and P9 dashboard output. This checks the current V1→F0 path (no new revision), not nonexistent future migrations or customer-specific data. Its source revision remains pinned for subsequent phases; any future model/helper incompatibility with that source must be resolved through a reviewed V1 fixture, never by silently changing the source to the new head. No test result on generated data certifies the customer's archive.

After reconciliation, rerun staff/owner login, receipt/reprint, reports (Today, This Month, custom range), CSV and closing acceptance on the copy. Record original invoice references and sequence values, profile/GST settings, row counts/hashes, monetary totals and report exports before/after. Keep those sensitive artifacts outside Git. Record target-only test sales separately from historical rows.

## 6. Migration/config incompatibilities and cutover ordering

Migration history is one operational chain: initial schema/report views → business settings/catalog/customer ledger/invoicing → sync foundation → multi-venture scope/enforcement → non-GST/menu/QR/orders/cloud links → Café billing → HC4 → P9 views → P10 governance → MFA (`0019`) → production marker (`0020`). `0020` is additive and refuses dropping a populated production marker. Cloud has its separate three-revision chain. F0 changes neither chain.

Known gaps blocking acceptance:

- C6 physical printer, reboot, real internet outage, installed timer and independent restore/copy evidence remain pending; V1 tag absent and deployed SHA unknown.
- Old Release Readiness / HC4 workflow assertions still expect `20260821_0019`; actual head is `20261018_0020`. Old backup CI uses `/tmp/kalpvrik-backups` outside configured data root, so its production guard refuses it. They were not changed on the protected V1 branch.
- Existing frontend audit reports high-severity `source-map-js@1.2.1`, patched at 1.2.2 (GHSA-68fv-2mgg-jv7q). Do not run automatic dependency fixes on the installed customer system. Review a release-candidate fix separately and forward-port intentionally.
- V1 services intentionally bind loopback and its health check requires the Café-only profile. LAN/multi-device V2 needs a separately tested profile/origin/firewall plan. Never expose PostgreSQL or silently repurpose the installed profile.
- Global company-name/code, user-email and tax-rate uniqueness need collision review before Retail provisioning. Do not change global tax rates to configure Retail if that changes Café behavior.
- No cross-OS restore or Windows scheduling certification yet. Do not promise runtime parity from wrapper presence.

Cutover is **not authorized or performed by F0**. First finish V1 acceptance and publish a reviewed immutable tag; verify its relationship to this base. If a V1 hotfix is required, preserve V1 history and deliberately forward-port the reviewed fix into V2. Reconcile any newer baseline, never rebase/retag to hide differences. Then complete all V2 phases and customer acceptance on isolated staging. Before approved cutover: freeze all financial/sync writers, verify a fresh backup and independent copy, record final reconciliation and old code/config, apply forward migrations, deploy tagged production build, restart and run health/smoke checks before reopening billing. Preserve legacy paths/service identifiers.

## 7. Rollback and recovery boundaries

- F0 is additive tooling/docs/CI only. Remove its development branch or make a normal revert if needed; no production rollback or database change is required. Never delete the protected V1 branch/tag.
- Failed migration: keep writers stopped; retain the verified archive, logs and old code/config. PostgreSQL transactional DDL usually rolls back, but verify actual revision/schema and any nontransactional operations. Do not assume an Alembic failure changed nothing. Prefer a reviewed forward repair.
- Failed health check after migration: switch code back only if old code is proven compatible with the resulting schema. No automatic Alembic downgrade, production restore, reset or reseed. Keep service unavailable if compatibility is uncertain.
- Restore recovery: first restore to a **new separate recovery database** and reconcile; the existing wrapper intentionally cannot overwrite production. An approved DBA cutover can then repoint services to that verified database, preserving the original database for investigation. Record keys/config/owners/extensions/grants as well as data; archives use `--no-owner --no-acl`, so privileges need deliberate reconstruction.
- **Data-loss boundary:** recovery to a backup discards every committed business operation after that backup unless those operations are independently recovered/reconciled. Once new-version sales resume, code rollback does not reverse invoices/payments/stock. Freeze writes and design a reconciled forward repair; never replay payments blindly. A pre-cutover backup with zero later accepted writes can provide zero business-transaction loss only after verification. Retention and restore testing alone do not establish zero RPO or a measured RTO.

## 8. Linux and Windows backup capability inventory

| Item | Linux | Windows |
| --- | --- | --- |
| Daily/manual archive | `backup_postgres.sh`, `pre_upgrade_backup.sh` → shared Python engine | `.ps1` equivalents → same engine |
| Restore | `restore_postgres.sh` guarded empty target | `restore_postgres.ps1` guarded empty target |
| Scheduling source | systemd timer 02:15 + random delay, `Persistent=true`; oneshot service, protected external env/data | `install_daily_backup.ps1`: Task Scheduler daily 02:15, SYSTEM, StartWhenAvailable, IgnoreNew |
| Default persistent storage | `/var/lib/kalpvrik` | `%PROGRAMDATA%/Kalpvrik` (legacy internal name) |
| Permissions | service account, umask 0077, archive mode 0600 | NTFS ACL and SYSTEM/Python/pg-tool access require actual-machine validation |
| Independent copy | No certified automatic independent-copy workflow | Same gap |
| Audit environment tools | Python 3.12.14, Node 24.19.0, npm 11.9.0; no pg_dump/pg_restore/psql/server/systemd acceptance | PowerShell/Task Scheduler unavailable here |

Record actual installed `SELECT version()`, `pg_dump --version`, `pg_restore --version`, Python version, archive size/checksum, job last/next run, exit code and restore reconciliation. Use dump/restore clients compatible with the source server (same major is preferred; never an older pg_dump than the server). Major PostgreSQL upgrades, Windows Task Scheduler certification, Windows ACL handling, Linux↔Windows extension/locale/encoding/timezone and cross-OS restore drills are V2 deliverables. Do not modify installed scheduling as part of this inventory. Preserve `/opt/kalpvrik` and `kalpvrik-*`; customer-facing branding is Kalpvriksh.

## 9. Phase evidence and exit gate

The new `full-v2-baseline.yml` runs on V2 pushes/PRs with a dedicated ephemeral PostgreSQL service, full Git history, mandatory populated-database and V1 browser tests, frontend checks, source guard and dependency audit. It does not deploy or reference customer secrets. It reports the known dependency-audit failure instead of suppressing it. Cloud integration tests still require isolated cloud test databases and are not certified by that job. Protect this job and require review of all changed V1 files in subsequent phases; a workflow file alone cannot configure GitHub branch protection.

Remote CI at V1 head: only the Vercel Preview Comments check was returned as successful. Earlier audit also returned Vercel deployment statuses; these do not prove release readiness. The new F0 workflow has not been remotely run as part of this local commit.

Fresh validation commands/results (development environment):

| Exact command | Result |
| --- | --- |
| `.venv/bin/python -m pytest backend/tests -q -rs` | 309 passed, 27 skipped, 3 warnings; 171.23 seconds |
| `.venv/bin/python -m pytest backend/tests/test_full_v2_baseline.py -q -rs` | 11 passed, 1 skipped; PostgreSQL drill not executed |
| `python scripts/check_cafe_v1_baseline.py` | 396 verified, no changed original files, no removals, V1 ancestor valid |
| `../.venv/bin/python -m alembic heads` (backend) | `20261018_0020` |
| `../.venv/bin/python -m alembic -c alembic_cloud.ini heads` (backend) | `20260821_cloud_0003` |
| `../.venv/bin/python -m alembic history` (backend) | One unbroken operational chain; no migration added |
| `npm run typecheck` (frontend) | PASS |
| `VITE_API_BASE_URL=http://127.0.0.1:8000/api npm run build` (frontend) | PASS; Vite large-chunk warning |
| `node --test tests/cafe-v1.test.mjs` (frontend) | 2 passed |
| `.venv/bin/python -m compileall -q backend/scripts/full_v2_baseline.py scripts/check_cafe_v1_baseline.py` | PASS |
| `bash -n scripts/backup_postgres.sh scripts/restore_postgres.sh scripts/pre_upgrade_backup.sh scripts/install_daily_backup.sh` | PASS, syntax only |
| `npm audit --omit=dev --audit-level=high --json` (frontend) | Known FAIL: one high advisory; no dependency modification |

The 27 skips are eight PostgreSQL integration tests (seven existing plus the new F0 drill), one V1 browser acceptance test and eighteen cloud tests. They are unverified gates, never waived. The prior recorded V1 report's 306/18 result is historical evidence, not this fresh run.

Modified files are additions only: this report, the source manifest, `scripts/check_cafe_v1_baseline.py`, `backend/scripts/full_v2_baseline.py`, `backend/tests/test_full_v2_baseline.py`, and `.github/workflows/full-v2-baseline.yml`. The full regression includes existing staff/login/report/idempotency/isolation tests. Initial new source-guard unit testing found an overly broad subprocess mock; it was corrected and the focused/full suites passed. No application behavior or migrations changed. **F0 cannot be marked complete until real populated snapshot migration/restore reconciliation, deployed baseline verification, required CI and V1 physical acceptance/tagging are proven.** No current production data or customer installation was accessed or modified.
