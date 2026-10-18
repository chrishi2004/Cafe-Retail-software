#!/usr/bin/env bash
# Run from the reviewed checkout installed at /opt/kalpvrik. Never seeds/migrates.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ "${1:-}" != prepare && "${1:-}" != activate ]]; then
  echo 'Usage: sudo bash scripts/install_cafe_linux.sh prepare|activate' >&2
  exit 2
fi
[[ "$EUID" -eq 0 ]] || { echo 'Run installation as root.' >&2; exit 1; }
[[ "$ROOT" == /opt/kalpvrik ]] || { echo 'Install the reviewed checkout at /opt/kalpvrik first.' >&2; exit 1; }
env_file=/etc/kalpvrik/local-hub.env
if [[ "$1" == prepare ]]; then
  for tool in systemctl python3 npm node pg_dump pg_restore useradd install runuser; do
    command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool" >&2; exit 1; }
  done
  python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
  node -e 'if (Number(process.versions.node.split(".")[0]) < 22) { throw Error("Node 22+ required for building") }'
  for unit in kalpvrik-api.service kalpvrik-frontend.service kalpvrik-backup.service; do
    if systemctl is-active --quiet "$unit"; then
      echo "Stop $unit before replacing dependencies/builds; see upgrade instructions." >&2
      exit 1
    fi
  done
  if systemctl cat kalpvrik-backup.timer >/dev/null 2>&1; then
    systemctl stop kalpvrik-backup.timer
  fi
  id kalpvrik >/dev/null 2>&1 || useradd --system --user-group --home-dir /var/lib/kalpvrik --shell /usr/sbin/nologin kalpvrik
  install -d -o root -g kalpvrik -m 0750 /etc/kalpvrik
  install -d -o kalpvrik -g kalpvrik -m 0750 /var/lib/kalpvrik /var/log/kalpvrik
  if [[ ! -e "$env_file" ]]; then
    install -o root -g kalpvrik -m 0640 "$ROOT/deploy/cafe-v1/local-hub.env.example" "$env_file"
  fi
  # Existing configuration, PostgreSQL cluster and backups are never replaced.
  python3 -m venv "$ROOT/backend/.venv"
  "$ROOT/backend/.venv/bin/python" -m pip install -r "$ROOT/backend/requirements.txt"
  (
    cd "$ROOT/frontend"
    npm ci
    # Ignore development env files when building this fixed local-only profile.
    VITE_API_BASE_URL=http://127.0.0.1:8000/api VITE_OPERATIONAL_API_BASE_URL=http://127.0.0.1:8000/api VITE_CLOUD_API_BASE_URL=http://127.0.0.1:8000/api npm run build
  )
  for unit in kalpvrik-api.service kalpvrik-frontend.service kalpvrik-backup.service kalpvrik-backup.timer; do
    install -m 0644 "$ROOT/deploy/systemd/$unit" "/etc/systemd/system/$unit"
  done
  for unit in kalpvrik-api.service kalpvrik-frontend.service; do
    install -d -m 0755 "/etc/systemd/system/$unit.d"
    install -m 0644 "$ROOT/deploy/cafe-v1/$unit.d/local-only.conf" "/etc/systemd/system/$unit.d/cafe-v1.conf"
  done
  install -d -m 0755 /usr/share/applications
  install -m 0644 "$ROOT/deploy/cafe-v1/kalpvrik-cafe.desktop" /usr/share/applications/kalpvrik-cafe.desktop
  # Runtime service cannot modify executable code or its build/dependencies.
  chown -R root:root "$ROOT"
  chmod -R a+rX "$ROOT"
  chmod -R go-w "$ROOT"
  systemctl daemon-reload
  echo 'Prepared. Configure the external environment, bootstrap NEW databases or upgrade existing ones, enroll owner MFA, then run activate. No database changes or service starts were performed.'
else
  [[ -f "$env_file" && -f "$ROOT/frontend/dist/index.html" ]] || { echo 'Run prepare and configure production first.' >&2; exit 1; }
  chown root:kalpvrik "$env_file"
  chmod 0640 "$env_file"
  systemctl enable --now postgresql.service
  runuser -u kalpvrik -- env KALPVRIK_ENV_FILE="$env_file" "$ROOT/backend/.venv/bin/python" "$ROOT/scripts/check_cafe_v1.py" --preflight
  # Existing optional components stay in the repository, outside this profile.
  for unit in kalpvrik-sync.service kalpvrik-menu-publish.timer kalpvrik-menu-publish.service; do
    if systemctl cat "$unit" >/dev/null 2>&1; then
      systemctl disable --now "$unit"
    fi
  done
  systemctl enable kalpvrik-api.service kalpvrik-frontend.service kalpvrik-backup.timer
  systemctl restart kalpvrik-api.service kalpvrik-frontend.service
  # First verified backup must succeed before activation reports success.
  systemctl start kalpvrik-backup.service
  systemctl start kalpvrik-backup.timer
  for attempt in {1..15}; do
    if runuser -u kalpvrik -- bash "$ROOT/scripts/check_cafe_v1.sh"; then
      echo 'Café V1 is ready at http://127.0.0.1:4173/ (desktop launcher: Kalpvrik Café).'
      exit 0
    fi
    sleep 2
  done
  echo 'Activation health check failed; inspect the service journals.' >&2
  exit 1
fi
