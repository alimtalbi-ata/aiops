#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
bash tests/static-audit.sh
bash tests/sql-audit.sh
bash tests/migration-contract.sh
bash tests/core-ledger-contract.sh
bash tests/backup-contract.sh
bash tests/temporal-contract.sh
bash -n deploy/*.sh deploy/temporal/*.sh tests/*.sh
python3 -m compileall -q app deploy tests tools
find app deploy tests tools -type d -name __pycache__ -prune -exec rm -rf {} +
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
VERSION="$(cat VERSION 2>/dev/null || echo 2.0.0-core)"
mkdir -p "$ROOT/dist"
command -v zip >/dev/null || { echo "FAIL|zip_missing"; exit 2; }
OUT="$ROOT/dist/AIOps-${VERSION}-Core-Deployment-Kit-${STAMP}.zip"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
GIT_TOPLEVEL="$(git -C "$ROOT" rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -n "$GIT_TOPLEVEL" && "$(cd "$GIT_TOPLEVEL" && pwd -P)" == "$ROOT" ]]; then
  git -C "$ROOT" archive --format=tar HEAD | tar -xf - -C "$TMP"
  SOURCE_PACKAGING_MODE="versioned_git_tree"
else
  # The kit must also be repackageable after extraction on a non-Git host.
  python3 deploy/package_tree.py --source "$ROOT" --destination "$TMP"
  SOURCE_PACKAGING_MODE="extracted_source_tree"
fi
mkdir -p "$TMP/09-Qualification"
QUALIFICATION="static-unit-only"
MODEL_QUALITY="NOT_RUN"
if [[ "${REQUIRE_RUNTIME_REPORT:-0}" == "1" ]]; then
  compgen -G "reports/runtime-e2e-*.json" >/dev/null || { echo 'FAIL|runtime_qualification_report_missing'; exit 3; }
  [[ -s reports/ai-core-evaluation.json ]] || { echo 'FAIL|ai_quality_report_missing'; exit 3; }
  python3 -c 'import json; r=json.load(open("reports/ai-core-evaluation.json",encoding="utf-8")); assert r.get("result")=="PASS" and r.get("ledger_persistence",{}).get("status")=="PASS" and r.get("qualification_kind")=="deterministic-integration-fixture", "AI evaluation not qualified"'
  python3 -c 'import json,sys; files=sys.argv[1:]; assert files, "no runtime report"; reports=[json.load(open(p,encoding="utf-8")) for p in files]; assert all(r.get("result")=="PASS" and r.get("live_execution")=="disabled" for r in reports), "runtime report not PASS or flag unexpected"' reports/runtime-e2e-*.json
  for report in reports/runtime-e2e-*.json reports/ai-core-evaluation.json; do
    [[ -f "$report" ]] && cp "$report" "$TMP/09-Qualification/"
  done
  QUALIFICATION="CI-runtime-e2e-PASS"
  MODEL_QUALITY="PASS"
fi
# An extracted kit may contain stale reports: never inherit CI acceptance without
# the explicit REQUIRE_RUNTIME_REPORT=1 gate and current machine-readable proofs.
GIT_COMMIT="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || true)"
if [[ -z "$GIT_COMMIT" || "$SOURCE_PACKAGING_MODE" != "versioned_git_tree" ]]; then
  GIT_COMMIT="$(sed -n 's/^git_commit=//p' "$ROOT/RELEASE-MANIFEST.txt" 2>/dev/null | head -1 || true)"
  [[ "$GIT_COMMIT" =~ ^[a-f0-9]{40}$ ]] || GIT_COMMIT="UNKNOWN_EXTRACTED_SOURCE"
fi
{
 echo "product=AIOps 2.0"
 echo "version=$VERSION"
 echo "source_packaging_mode=$SOURCE_PACKAGING_MODE"
 echo "built_utc=$STAMP"
 echo "git_commit=$GIT_COMMIT"
 echo "qualification=$QUALIFICATION"
 echo "synthetic_analyst_critic_quality=$MODEL_QUALITY"
 echo "real_model_qualification=NOT_RUN"
 echo "production_qualification=NOT_RUN"
 echo "ci_evidence_carried=$([[ "$QUALIFICATION" == "CI-runtime-e2e-PASS" ]] && echo yes || echo no)"
 echo "author=Abdelhalim Talbi"
} > "$TMP/RELEASE-MANIFEST.txt"
# Reconcile the tracked historical V8 inventory against the exact staged kit.
# Fail closed on absent, unsafe or inconsistent paths before hashing the archive.
python3 deploy/refresh_release_inventory.py --root "$TMP" --release "$VERSION"
(cd "$TMP" && find . -type f ! -name FILES-SHA256SUMS -print0 | sort -z | xargs -0 sha256sum) > "$TMP/FILES-SHA256SUMS"
(
 cd "$TMP"
 zip -qr "$OUT" . -x '.env' '.git/*' '*__pycache__*' '*.pyc' 'backups/*' 'reports/*' '.venv/*'
)
unzip -tqq "$OUT" >/dev/null || { echo "FAIL|zip_integrity_check"; exit 4; }
( cd "$(dirname "$OUT")" && sha256sum "$(basename "$OUT")" ) > "$OUT.sha256"
echo "PACKAGE=$OUT"
echo "CHECKSUM=$OUT.sha256"
echo "PACKAGE_EXCLUDES=.env,git metadata,backups,reports,python caches"
