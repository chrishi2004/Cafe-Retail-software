#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
install -m 0644 "${ROOT}/deploy/systemd/kalpvrik-backup.service" /etc/systemd/system/kalpvrik-backup.service
install -m 0644 "${ROOT}/deploy/systemd/kalpvrik-backup.timer" /etc/systemd/system/kalpvrik-backup.timer
systemctl daemon-reload
systemctl enable --now kalpvrik-backup.timer
systemctl start kalpvrik-backup.service
systemctl --no-pager status kalpvrik-backup.timer
