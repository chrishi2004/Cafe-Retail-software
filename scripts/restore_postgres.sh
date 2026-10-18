#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${KALPVRIK_PYTHON:-${ROOT}/backend/.venv/bin/python}"
exec "${PYTHON}" "${ROOT}/backend/scripts/cafe_production.py" restore "$@"
