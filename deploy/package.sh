#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
bash tests/static-audit.sh
bash tests/sql-audit.sh
bash tests/migration-contract.sh
bash tests/core-ledger-contract.sh
bash tests/backup-contract.sh
python3 -m compileall -q app tests
find app tests -type d -name __pycache__ -prune -exec rm -rf {} +
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
VERSION="$(cat VERSION 2>/dev/null || echo 2.0.0-core)"
mkdir -p "$ROOT/dist"
command -v zip >/dev/null || { echo "FAIL|zip_missing"; exit 2; }
OUT="$ROOT/dist/AIOps-${VERSION}-Core-Deployment-Kit-${STAMP}.zip"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git archive --format=tar HEAD | tar -xf - -C "$TMP"
mkdir -p "$TMP/09-Qualification"
if [[ "$(printenv REQUIRE_RUNTIME_REPORT || true)" == "1" ]]; then
  compgen -G "reports/runtime-e2e-*.json" >/dev/null || { echo 'FAIL|runtime_qualification_report_missing'; exit 3; }
  python3 -c 'import json,sys; files=sys.argv[1:]; assert files, "no runtime report"; reports=[json.load(open(p,encoding="utf-8")) for p in files]; assert all(r.get("result")=="PASS" and r.get("live_execution")=="disabled" for r in reports), "runtime report not PASS or live flag unexpected"' reports/runtime-e2e-*.json
fi
for report in reports/runtime-e2e-*.json; do [[ -f "$report" ]] && cp "$report" "$TMP/09-Qualification/"; done
QUALIFICATION="static-unit-only"
compgen -G "$TMP/09-Qualification/runtime-e2e-*.json" >/dev/null && QUALIFICATION="CI-runtime-e2e-PASS"
{
 echo "product=AIOps 2.0"
 echo "version=$VERSION"
 echo "built_utc=$STAMP"
 echo "git_commit=$(git rev-parse HEAD)"
 echo "qualification=$QUALIFICATION"
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
