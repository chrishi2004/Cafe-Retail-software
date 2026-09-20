#!/usr/bin/env bash
set -euo pipefail
umask 077

: "${LOCAL_BACKUP_DATABASE_URL:?Set LOCAL_BACKUP_DATABASE_URL to a pg_dump-compatible PostgreSQL URL}"

BACKUP_ROOT="${KALPVRIK_BACKUP_ROOT:-/var/lib/kalpvrik/backups/postgres}"
RETENTION_DAYS="${KALPVRIK_BACKUP_RETENTION_DAYS:-30}"
[[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]] && (( RETENTION_DAYS >= 1 )) || { echo "Retention must be at least one day." >&2; exit 1; }
STAMP="$(date -u +%Y%m%d_%H%M%S)_$$"
MONTH="$(date -u +%Y-%m)"
DEST_DIR="${BACKUP_ROOT}/${MONTH}"
DEST="${DEST_DIR}/kalpvrik_${STAMP}.dump"
TMP="${DEST}.tmp"

install -d -m 0750 "${DEST_DIR}"
trap 'rm -f "${TMP}"' EXIT

pg_dump "${LOCAL_BACKUP_DATABASE_URL}" --format=custom --no-owner --no-acl --file="${TMP}"
pg_restore --list "${TMP}" >/dev/null
mv "${TMP}" "${DEST}"
sha256sum "${DEST}" > "${DEST}.sha256"
find "${BACKUP_ROOT}" -type f \( -name '*.dump' -o -name '*.dump.sha256' \) -mtime +"${RETENTION_DAYS}" -delete

echo "Backup created and verified: ${DEST}"
