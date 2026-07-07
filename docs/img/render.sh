#!/usr/bin/env bash
# Regenerate the documentation diagrams: each hand-authored <name>.svg -> <name>.png.
# Rendered locally with headless Google Chrome at 2x device scale (crisp, real
# system fonts) — no Node, no mermaid, no external service. Run from anywhere.
set -euo pipefail
cd "$(dirname "$0")"

CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

for svg in *.svg; do
  name="${svg%.svg}"
  w="$(grep -oE 'width="[0-9]+"' "$svg" | head -1 | grep -oE '[0-9]+')"
  h="$(grep -oE 'height="[0-9]+"' "$svg" | head -1 | grep -oE '[0-9]+')"
  { printf '<!doctype html><meta charset="utf-8"><style>html,body{margin:0;padding:0}</style>'
    cat "$svg"; } > "$tmp/page.html"
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars \
    --force-device-scale-factor=2 --window-size="$w,$h" \
    --screenshot="$name.png" "file://$tmp/page.html" >/dev/null 2>&1
  echo "rendered $name.png (${w}x${h} @2x)"
done
