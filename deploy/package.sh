#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
rm -rf app/**/__pycache__ 2>/dev/null || true
bash tests/static-audit.sh
bash tests/sql-audit.sh
python3 -m compileall -q app
find app -type d -name __pycache__ -prune -exec rm -rf {} +
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="../AIOps-2.0-Final-BigBang-Deployment-Kit-${STAMP}.zip"
zip -qr "$OUT" . -x '*.pyc' -x '.env' -x '.git/*'
sha256sum "$OUT" > "$OUT.sha256"
echo "PACKAGE=$OUT"
