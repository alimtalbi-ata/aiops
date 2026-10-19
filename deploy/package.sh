#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
bash tests/static-audit.sh
bash tests/sql-audit.sh
bash tests/migration-contract.sh
python3 -m compileall -q app tests
find app tests -type d -name __pycache__ -prune -exec rm -rf {} +
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
VERSION="$(grep -m1 -E 'version|Version' README.md 2>/dev/null | tr -cd 'A-Za-z0-9._-' | head -c 24 || echo AIOps2)"
mkdir -p "$ROOT/dist"
command -v zip >/dev/null || { echo "FAIL|zip_missing"; exit 2; }
OUT="$ROOT/dist/AIOps-2.0-Core-Deployment-Kit-${STAMP}.zip"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git archive --format=tar HEAD | tar -xf - -C "$TMP"
{
 echo "product=AIOps 2.0"
 echo "version=$VERSION"
 echo "built_utc=$STAMP"
 echo "git_commit=$(git rev-parse HEAD)"
 echo "qualification=static-and-unit-only-unless-runtime-report-included"
 echo "author=Abdelhalim Talbi"
} > "$TMP/RELEASE-MANIFEST.txt"
find "$TMP" -type f ! -name FILES-SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > "$TMP/FILES-SHA256SUMS"
(
 cd "$TMP"
 zip -qr "$OUT" . -x '.env' '.git/*' '*__pycache__*' '*.pyc' 'backups/*' 'reports/*' '.venv/*'
)
sha256sum "$OUT" > "$OUT.sha256"
echo "PACKAGE=$OUT"
echo "CHECKSUM=$OUT.sha256"
echo "PACKAGE_EXCLUDES=.env,git metadata,backups,reports,python caches"
