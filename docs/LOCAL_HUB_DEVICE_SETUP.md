# Local Hub device setup

For the Café V1 production release, follow [Café production data and upgrades](CAFE_PRODUCTION_DATA.md). That guide replaces the older demo-seed installation procedure.

- Install the supported PostgreSQL server/client tools and keep its persistent data directory across code upgrades.
- Keep production configuration and backups outside the checkout: `C:/ProgramData/Kalpvrik` on Windows or `/etc/kalpvrik` plus `/var/lib/kalpvrik` on Linux.
- For a **new empty installation**, use `backend/scripts/cafe_production.py bootstrap` with real Café details. Do not run Alembic manually before that bootstrap.
- For an **existing installation**, use `scripts/upgrade_cafe.ps1` or `scripts/upgrade_cafe.sh`; these verify a pre-upgrade backup and run Alembic without reseeding.
- Install the daily backup task/timer and complete a restore drill to a separate disposable database before accepting live sales.
- Enroll privileged MFA using [MFA production setup](MFA_PRODUCTION_SETUP.md).

The repository's `seed*.py` scripts are for isolated development/demo databases. They are not production installation or upgrade commands, and production guards now refuse them against marked or non-demo databases.

The existing `start_local_hub.ps1` remains a development convenience that starts API/frontend processes; it does not install persistent services, provision the production database or seed data. Use the production service/task setup for unattended operation. Never copy a virtual environment, demo database or credentials from a development machine onto the customer installation.
