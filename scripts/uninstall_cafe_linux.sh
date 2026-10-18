#!/usr/bin/env bash
# Remove app integration only. Intentionally contains no database administration.
set -euo pipefail
if [[ "${1:-}" != --keep-code && "${1:-}" != --remove-code ]]; then
  echo 'Usage: sudo bash scripts/uninstall_cafe_linux.sh --keep-code|--remove-code' >&2
  exit 2
fi
[[ "$EUID" -eq 0 ]] || { echo 'Run uninstall as root.' >&2; exit 1; }
for unit in kalpvrik-api.service kalpvrik-frontend.service kalpvrik-backup.timer kalpvrik-backup.service; do
  if systemctl cat "$unit" >/dev/null 2>&1; then
    systemctl disable --now "$unit"
  fi
  rm -f "/etc/systemd/system/$unit"
done
# Remove only this profile's drop-ins, leaving any operator customizations.
rm -f /etc/systemd/system/kalpvrik-api.service.d/cafe-v1.conf /etc/systemd/system/kalpvrik-frontend.service.d/cafe-v1.conf
rm -f /usr/share/applications/kalpvrik-cafe.desktop
systemctl daemon-reload
if [[ "$1" == --remove-code ]]; then
  [[ ! -L /opt/kalpvrik ]] || { echo 'Refusing symlinked application path.' >&2; exit 1; }
  rm -rf -- /opt/kalpvrik
fi
echo 'Application removed/stopped. PostgreSQL, /etc/kalpvrik and /var/lib/kalpvrik were retained. Daily application backups are now stopped; reinstall to resume them.'
