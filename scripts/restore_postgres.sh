#!/usr/bin/env bash
# Restore only into an existing, empty database. Never clean or overwrite a database.
set -euo pipefail
umask 077
: "${LOCAL_RESTORE_DATABASE_URL:?Set LOCAL_RESTORE_DATABASE_URL to a separate empty PostgreSQL database}"
DUMP="${1:?Usage: restore_postgres.sh /path/to/backup.dump}"
[[ -f "$DUMP" && -f "${DUMP}.sha256" ]] || { echo 'Backup or checksum missing.' >&2; exit 1; }
EXPECTED="$(awk 'NR==1 {print $1}' "${DUMP}.sha256")"
ACTUAL="$(sha256sum "$DUMP" | awk '{print $1}')"
[[ "$EXPECTED" =~ ^[0-9a-f]{64}$ && "$EXPECTED" == "$ACTUAL" ]] || { echo 'Checksum mismatch.' >&2; exit 1; }
pg_restore --list "$DUMP" >/dev/null
# Pass the URL directly so libpq uses its host/port instead of treating the URL
# as a database name and falling back to a local Unix socket.
COUNT="$(psql "$LOCAL_RESTORE_DATABASE_URL" -X -v ON_ERROR_STOP=1 -tAc "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%' AND c.relkind IN ('r','p','v','m','S','f')")"
[[ "$COUNT" == 0 ]] || { echo 'Refusing restore: target contains database objects.' >&2; exit 1; }
# The target has been proven empty; restore atomically and never drop objects.
pg_restore --dbname="$LOCAL_RESTORE_DATABASE_URL" --single-transaction --exit-on-error --no-owner --no-privileges "$DUMP"
psql "$LOCAL_RESTORE_DATABASE_URL" -X -v ON_ERROR_STOP=1 -tAc 'SELECT version_num FROM alembic_version'
echo 'Restore completed. Compare record counts and financial totals before using the restored database.'
