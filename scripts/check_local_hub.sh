#!/usr/bin/env bash
set -euo pipefail

API_URL="${KALPVRIK_API_HEALTH_URL:-http://127.0.0.1:8000/api/health}"
UI_URL="${KALPVRIK_UI_URL:-http://127.0.0.1:4173/}"

fail=0

check_service() {
  local name="$1"
  if systemctl is-active --quiet "$name"; then
    printf '[OK]   %s\n' "$name"
  else
    printf '[FAIL] %s\n' "$name"
    fail=1
  fi
}

check_url() {
  local label="$1"
  local url="$2"
  if curl --fail --silent --show-error --max-time 5 "$url" >/dev/null; then
    printf '[OK]   %s %s\n' "$label" "$url"
  else
    printf '[FAIL] %s %s\n' "$label" "$url"
    fail=1
  fi
}

check_service postgresql.service
check_service kalpvrik-api.service
check_service kalpvrik-sync.service
check_service kalpvrik-frontend.service
check_url 'API' "$API_URL"
check_url 'UI ' "$UI_URL"

if [[ "$fail" -ne 0 ]]; then
  echo 'Local Hub health check failed.' >&2
  exit 1
fi

echo 'Local Hub is healthy.'
