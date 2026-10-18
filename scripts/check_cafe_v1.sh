#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export KALPVRIK_ENV_FILE="${KALPVRIK_ENV_FILE:-/etc/kalpvrik/local-hub.env}"
exec "${ROOT}/backend/.venv/bin/python" "${ROOT}/scripts/check_cafe_v1.py" "$@"
