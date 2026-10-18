#!/usr/bin/env bash
set -euo pipefail
url=http://127.0.0.1:4173/
# Run as the desktop user; keep browser state outside replaceable application code.
for browser in chromium chromium-browser google-chrome-stable google-chrome brave-browser; do
  if command -v "$browser" >/dev/null 2>&1; then
    exec "$browser" --app="$url" --user-data-dir="${XDG_CONFIG_HOME:-$HOME/.config}/kalpvrik-cafe" "$@"
  fi
done
if command -v firefox >/dev/null 2>&1; then
  exec firefox --new-window "$url"
fi
exec xdg-open "$url"
