#!/usr/bin/env bash
set -euo pipefail

OUT="_cloudflare_site"
rm -rf "$OUT"
mkdir -p "$OUT"

# Publish only browser-facing assets. Do not expose backend/, contracts/, docs/,
# tests/, workflows, or repository-internal material through the UAT site.
cp index.html app.html preview.html "$OUT"/
cp -R assets "$OUT"/assets
cp -R src "$OUT"/src

test -f "$OUT/index.html"
test -f "$OUT/app.html"
test -f "$OUT/src/app.css"

echo "KU2A Cloudflare preview staged at $OUT"
