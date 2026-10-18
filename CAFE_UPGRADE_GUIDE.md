# Kalpvriksh Café: production upgrades

PostgreSQL persists across every release. Upgrades replace application code/dependencies/builds and apply forward Alembic migrations to the **same database**, preserving users, orders, invoices, payments, menu, inventory, closing records and historical reports. Never bootstrap, demo-seed, reset, stamp, downgrade or drop/recreate production to upgrade it.

## Prerequisites

- Use the [Linux production layout](docs/CAFE_V1_LINUX.md): `/opt/kalpvrik`, `/etc/kalpvrik/local-hub.env`, `/var/lib/kalpvrik`. Retain PostgreSQL's cluster and `SECRET_KEY`.
- Maintainers publish immutable, reviewed tags (`cafe-v1.0.0`, `cafe-v1.1.0`, etc.) containing this workflow, maintenance CLI and Café health checks. Test forward migrations against a restored copy of the previous release's data. Never move/reuse published tags.
- Installed Git HEAD must be clean and have exactly one published `cafe-vX.Y.Z` tag. For initial branch deployments, install the reviewed workflow once using the existing pre-tag procedure, then fetch the maintainer's first matching release tag. Do not invent customer-side version tags. This script does not publish releases.
- Have Node 22+, npm, Git, Python, matching PostgreSQL clients, installation-time network access and disk space for two backups/builds. Complete a disposable-database restore drill. Close all POS browsers and keep staff out until verification finishes.

## Upgrade

```bash
cd /opt/kalpvrik
sudo git describe --tags --exact-match HEAD
sudo bash scripts/upgrade_cafe_release.sh cafe-v1.1.0
```

Use the actual published target tag. Shell/development database settings are ignored; application configuration comes from the external production file. The script:

1. Verifies installed tag/commit and baseline Café health, refuses active optional writers, and acquires an exclusive upgrade lock.
2. Records database identity/revision; disables/stops API, frontend and backup timer; waits for any active backup. PostgreSQL stays running.
3. Creates a pre-upgrade backup with the installed version and independently verifies checksum, database identity, archive contents and full `pg_restore` decoding **before checkout**.
4. Fetches the exact tag without force, verifies a newer version and descendant commit, checks required files, and checks out that pinned commit detached. Dirty trees, moved local tag conflicts and unrelated history are refused.
5. Installs backend requirements and frontend dependencies (`npm ci`).
6. Reuses the guarded database upgrade: another verified backup followed by transactional Alembic `upgrade head`, without seeds or resets.
7. Builds production React, restarts/enables API/frontend and the backup timer, then runs local Café health checks. No cloud, sync, QR, AI or Vite development server is required.

The root-only `/var/lib/kalpvrik/upgrades/<run>/` journal contains `state.json`, command output and a copy of the initiating runner. It records previous/target commits, backup location, migration stage and final outcome. Backups/checksums/manifests remain under `/var/lib/kalpvrik/backups/postgres` with at least 30 days' retention. Keep an off-device copy.

Before reopening, verify cashier/owner login, receipt reprint, invoice/payment totals, stock, closing history, reports and `systemctl list-timers kalpvrik-backup.timer`. Stay at the pinned tag; do not use `git pull` for routine releases. OS/PostgreSQL major upgrades and service-layout changes require separate reviewed procedures.

## Failure and safe rollback

Handled failures disable/stop the app and timer, retaining PostgreSQL/data/backups. **No automatic code downgrade or database restore runs.** Inspect the printed journal path and service journals. After process/power interruption, check journal stage, Git HEAD, actual schema revision and service state before retrying; keep the counter closed.

Inspect the revision with a compatible maintenance environment:

```bash
sudo -u kalpvrik env -i PATH=/usr/bin:/bin KALPVRIK_ENV_FILE=/etc/kalpvrik/local-hub.env /opt/kalpvrik/backend/.venv/bin/python /opt/kalpvrik/backend/scripts/cafe_production.py status
```

- **Before migration, or verified transaction rollback:** compare actual schema/data with `previous_database` in `state.json`. A `migrations_started` flag alone does not prove rollback. Code rollback is allowed only if the previous application supports the actual schema/data. Use the recorded `previous_commit`, reinstall dependencies and rebuild, without migrations:

  ```bash
  sudo systemctl disable --now kalpvrik-api.service kalpvrik-frontend.service kalpvrik-backup.timer
  sudo git -C /opt/kalpvrik checkout --detach PREVIOUS_COMMIT_FROM_JOURNAL
  sudo bash /opt/kalpvrik/scripts/install_cafe_linux.sh prepare
  sudo bash /opt/kalpvrik/scripts/install_cafe_linux.sh activate
  ```

  The health check requires that version's schema head. If it rejects a newer schema, stop; never bypass it with stamp/reset/downgrade.
- **Migration committed or compatibility uncertain:** preserve current data, including transactions possibly accepted during health verification. Prefer a reviewed forward-fix release based on the failed target. A maintainer must resolve/validate the failure before restarting or retrying; baseline health intentionally blocks blind retries. If dependencies are broken, use a known-good release with an isolated matching virtual environment for inspection/backup.
- **Backup recovery:** follow the [restore procedure](docs/CAFE_PRODUCTION_DATA.md#restore-into-a-separate-disposable-database) into a separate empty `cafe_restore_*` database. Verify business totals/history. Cutover requires an explicit operator decision: stop writers, preserve current data/configuration, reconcile every newer transaction, switch local/backup URLs to the verified replacement and run compatible code. Retain the original database untouched. Never overwrite production with an older dump.

After recovery, confirm business history, resume/verify daily backups and test reboot behaviour on the installed machine.
