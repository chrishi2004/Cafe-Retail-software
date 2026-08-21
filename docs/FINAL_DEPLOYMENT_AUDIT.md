# Final Deployment and Branch Integration Audit

Audit date: 2026-08-21

Repository: `chrishi2004/Cafe-Retail-software`

Release branch: `agent/release-readiness-finalization`

Base `main` commit audited: `c2412290be801d1cd7c7704606fc6edb291d2158`

## Executive verdict

The repository is **architecturally feasible and implementation-ready for final environment deployment** using the approved hybrid model:

- customer QR/menu/order/status/bill-request is cloud-primary;
- POS, waiter, kitchen, billing, inventory, purchasing, governance and authoritative AI business tools are Local-Hub operational workloads;
- Local PostgreSQL remains the final system of record for invoices, payments, ledgers, stock, audit and other financial effects;
- Supabase is coordination/continuity storage, not an unrestricted operational database;
- remote Super Admin uses the hosted UI but reaches the Local Hub through an approved HTTPS tunnel/private network for live operational data/writes;
- Local Hub continues core operations during internet loss;
- cloud customer orders remain durable while the Local Hub is unavailable and converge after recovery.

No further architecture redesign is required before deployment. Remaining release work after this branch passes its automated gate is provider/physical-environment configuration and evidence, not another application phase.

## Branch audit

All repository branches visible during the audit were compared with `main`.

| Branch | Relationship to `main` | Disposition |
| --- | --- | --- |
| `main` | canonical current base | keep |
| `agent/release-readiness-finalization` | cleanly ahead, not behind | final integration candidate |
| `agent/r1-portable-local-hub` | no unique commits left | already absorbed by `main`; historical |
| `agent/r2-role-separated-product` | no unique commits left | already absorbed by `main`; historical |
| `agent/r3-cloud-customer-continuity` | no unique commits left | already absorbed by `main`; historical |
| `agent/r4-cloud-deployment-readiness` | no unique commits left | already absorbed by `main`; historical |
| `audit/reconcile-p6-hc2-reports` | no unique commits left | already absorbed by `main`; historical |
| `phase/p9-cafe-consolidated-dashboards` | divergent ancestry | P9 implementation already present; historical |
| `phase/p10-closing-audit-purge` | divergent ancestry | P10 implementation already present; historical |
| `phase/p11-security-hardening-release` | divergent ancestry | P11 implementation already present; historical |
| `agent/laptop-migration-handoff` | one documentation-only commit ahead | superseded by current Linux/cloud release docs; do not merge as-is |

The P9/P10/P11 histories diverge because of the way phase PRs were integrated, not because production implementation is missing. Key implementation files were compared directly and are byte-identical between the old phase branches and the release branch:

- P9 reporting service;
- P10 governance service;
- P11 security-hardening core.

Historical PRs for P9, P10, P11 and R1-R4 are already merged into `main`. The open laptop-migration PR is a Windows-era handoff document and records an older cloud migration revision, so it should be treated as superseded rather than merged into the final release.

## Final deployment architecture

```text
CUSTOMER PHONE
    |
    | QR / hosted link
    v
HOSTED REACT FRONTEND
    |
    +------------------------------+
    |                              |
    | customer path                | staff / owner path
    v                              v
RESTRICTED CLOUD GATEWAY        HTTPS TUNNEL / PRIVATE NETWORK
    |                              |
    v                              v
SUPABASE COORDINATION           LOCAL HUB FASTAPI
    |                              |
    | durable commands/events      +--> Local PostgreSQL (authority)
    +----------------------------->+--> Sync worker
                                   +--> Local PWA
                                   +--> Backup timer
                                   +--> Cafe menu publication timer
```

### Authority boundary

Cloud may hold only approved coordination/continuity data such as:

- published customer-safe Cafe menu/QR snapshot;
- cloud customer order intake;
- customer-safe order status;
- durable bill-request command;
- device heartbeat/lease/fencing state;
- synchronization commands/receipts;
- approved sanitized snapshots.

Cloud must not become authoritative for:

- invoice issuance;
- payment posting;
- customer ledger balance;
- authoritative inventory/stock movement;
- business closing/reversal/purge governance;
- unrestricted operational database access.

## Release defects found and closed during final audit

### 1. Cloud gateway URL duplication

The runbook historically configured a gateway value ending in `/api`, while the transport appended `/api/...`. That could produce `/api/api/...` for heartbeat/sync/publication calls.

Fixed by central gateway URL normalization. Both forms are now supported:

```text
https://gateway.example.com
https://gateway.example.com/api
```

Both resolve to exactly one `/api` prefix.

### 2. Business-group sync isolation

Business-group-scoped Local Hub devices could previously rely too heavily on submitted envelope scope when pulling/acknowledging/pushing synchronization data.

Fixed by:

- always filtering command pull by registered `business_group_id`;
- validating receipt acknowledgements against the stored command scope;
- authorizing Cafe order status events against the stored cloud-order scope before accepting the submitted event.

Dedicated release regression proves a business-group device cannot pull or acknowledge another group's command.

### 3. Missing trusted Local Hub device registration workflow

The runtime supported authenticated devices, but the deployment documentation did not previously have a clean production command to create/update the registration.

Added:

```bash
python -m scripts.register_cloud_device
```

Properties:

- uses the stable Local Hub device identity;
- validates local business-group/company/branch scope;
- stores only `sha256(SYNC_DEVICE_SECRET)` in cloud coordination;
- never prints or stores the raw secret in cloud;
- refuses accidental credential replacement;
- supports deliberate `--rotate-secret`;
- authorizes only heartbeat/menu-publication/sync-pull/sync-push by default.

### 4. Missing production Cafe cloud publication workflow

Cloud-primary QR ordering requires a current safe menu/table/QR snapshot. The builder existed, but no production command/timer previously executed it.

Added:

```bash
python -m scripts.publish_cafe_menu --force
```

and systemd units:

```text
kalpvrik-menu-publish.service
kalpvrik-menu-publish.timer
```

The timer checks frequently but the publisher persists a non-secret content fingerprint and skips unchanged snapshots, avoiding continuous duplicate menu versions.

### 5. Deployment-document configuration mismatch

The Linux guide referred to `CORS_ORIGINS`, but the application configuration uses:

```text
FRONTEND_ORIGIN
FRONTEND_EXTRA_ORIGINS
```

The runbooks and environment template now match the actual application settings.

### 6. Release workflow only protected the release branch

`Release Readiness` now also runs on pull requests into `main`, so the final integration cannot rely only on older phase workflows.

## Automated release evidence required

The unified `.github/workflows/release-readiness.yml` now verifies:

- Local Hub migration -> `20260821_0019`;
- Cloud coordination migration -> `20260821_cloud_0003`;
- independent local/cloud migration histories;
- privileged TOTP MFA/recovery behavior;
- cloud gateway URL normalization;
- business-group sync isolation;
- cloud bill-request safety;
- cloud menu/order convergence;
- Local Hub recovery/reconciliation;
- Cafe billing idempotency/stock safety;
- company/cross-venture isolation;
- complete backend regression;
- Python compilation including operator scripts;
- Linux shell script syntax;
- Python dependency audit;
- real `pg_dump`, SHA-256 verification and restore into a fresh PostgreSQL database;
- frontend typecheck/build;
- browser source secret scan;
- Chromium release smoke;
- production npm dependency audit.

A merge into `main` should not be treated as production-approved until this gate is green for the exact final PR head.

## Deployment feasibility by workload

| Workload | Final location | Feasibility |
| --- | --- | --- |
| Customer QR/menu | Hosted frontend + Cloud Gateway | ready for provider configuration |
| Customer order submit | Cloud Gateway + Supabase durable coordination | implemented |
| Cloud -> Local order convergence | Local sync worker | implemented |
| Request Bill | durable cloud command -> Local Hub session state | implemented; no cloud finance effect |
| POS billing | Local Hub | implemented |
| Waiter operations | Local Hub over LAN | implemented |
| Kitchen operations | Local Hub over LAN | implemented |
| Multi-user concurrent access | one shared Local Hub API/PostgreSQL | supported and tested at application level |
| Remote Super Admin | hosted UI -> secure Local Hub endpoint | implemented architecture; tunnel must be configured in real environment |
| Local internet outage | Local LAN + Local Hub | designed to continue |
| Local Hub outage | customer cloud intake remains durable | implemented continuity behavior |
| Backup/recovery | systemd timer + PostgreSQL dump/restore | repository gate implemented; real external backup target still required |
| Privileged MFA | Local Hub auth | implemented; real accounts must be enrolled |
| Future invoice OCR/AI feed | Local Hub worker/review flow | intentionally later enhancement, not current release blocker |

## Merge policy

The release branch should connect to `main` through one reviewed PR. Do not direct-force-update `main` and do not merge old phase branches into the release branch merely to make Git ancestry look linear.

Merge when all of the following are true:

1. release branch is still `0 behind main`;
2. `Release Readiness` is green for the exact PR head;
3. Vercel frontend and Cloud Gateway checks succeed for the exact PR head, or a documented provider-rate-limit condition has cleared and the final deployment succeeds;
4. no unresolved review blocker remains;
5. release migration heads remain `20260821_0019` and `20260821_cloud_0003`.

## External/physical work still required after repository merge

Repository CI cannot manufacture evidence for the real network/hardware/provider environment. The deployment operator must still:

1. create/select the production Supabase project and configure protected URLs;
2. apply cloud migration `20260821_cloud_0003` to that exact database;
3. configure the final Vercel frontend and Cloud Gateway environment variables;
4. allow Vercel build-rate limits to clear and obtain successful final deployments if preview builds are currently rate-limited;
5. install the exact release on the physical Local Hub;
6. apply Local Hub migration `20260821_0019`;
7. configure private PostgreSQL networking and prove TCP 5432 is not public;
8. configure the approved Cloudflare/Tailscale/private operational endpoint;
9. register the Local Hub device with `scripts.register_cloud_device`;
10. publish the first Cafe snapshot with `scripts.publish_cafe_menu --force` and verify its timer;
11. enroll the real Super Admin/Venture Admin accounts in MFA and store recovery codes offline;
12. scan a physical QR from a normal phone/mobile network and place an order;
13. test POS + waiter + kitchen + owner concurrently on the actual LAN;
14. test internet loss, Local Hub restart, queue recovery and duplicate delivery;
15. run a real backup to storage independent of the Hub SSD and restore it;
16. validate printing, UPS behavior and controlled recovery;
17. configure real provider/edge rate limits and trusted proxy settings;
18. complete every applicable item in `docs/PRODUCTION_GO_LIVE_CHECKLIST.md`.

## Final recommendation

Treat `agent/release-readiness-finalization` as the only release candidate branch. Do not pull implementation back from stale P9/P10/P11 branches or the Windows laptop handoff branch.

Once the final PR gate and provider checks are green, merge this release branch into `main`, deploy that exact merge/release commit, and complete the physical/provider go-live checklist. At that point, further product development such as purchase-bill OCR/local LLM enhancements can start as a separate post-release phase without changing the core deployment architecture.
