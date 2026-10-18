#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
command -v zip >/dev/null || { echo 'FAIL|ZIP_MISSING';exit 1; }
bash tests/static-audit.sh
bash tests/sql-audit.sh
python3 -m compileall -q app
find app -type d -name __pycache__ -prune -exec rm -rf {} +
[ -s images/images.tar ] || { echo 'FAIL|EXPORT_DOCKER_IMAGES_FIRST';exit 1; }
(cd images && sha256sum -c images.sha256)
OUT="${AIOPS2_PACKAGE_OUTPUT:-$ROOT/../AIOps-2.0-R5-Debian-Offline.zip}"
[ ! -e "$OUT" ] || { echo "FAIL|OUTPUT_EXISTS|$OUT";exit 1; }
zip -qr "$OUT" . -x '.git/*' -x '.env' -x '*.pyc' -x '*/__pycache__/*'
sha256sum "$OUT" > "$OUT.sha256"
unzip -t "$OUT" >/dev/null
echo "PACKAGE=$OUT"
