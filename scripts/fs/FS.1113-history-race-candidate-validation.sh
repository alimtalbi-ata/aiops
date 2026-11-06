#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
PROD=aiops2-rebuild-portal
EXPECTED_PROD=aiops2-portal:fs1073-csp-candidate

echo "FS1113_MODE=NONPRODUCTION_HISTORY_RACE_FIX_BUILD_AND_FULL_BROWSER_GATE"
PROD_BEFORE="$(docker inspect "$PROD" --format '{{.Config.Image}}')"
echo "FS1113_PRODUCTION_IMAGE_BEFORE=$PROD_BEFORE"
[[ "$PROD_BEFORE" == "$EXPECTED_PROD" ]] || {
  echo "FS1113_ERROR=UNEXPECTED_PRODUCTION_IMAGE"
  exit 2
}

# Always rebuild from the current branch patch; never trust a cached candidate tag.
bash "$ROOT/scripts/fs/FS.1097-build-history-chart-candidate.sh"

# Reuse the validated publish-first network lifecycle and full Chromium matrix.
bash "$ROOT/scripts/fs/FS.1107-full-history-candidate-external-first-browser.sh"

PROD_AFTER="$(docker inspect "$PROD" --format '{{.Config.Image}}')"
echo "FS1113_PRODUCTION_IMAGE_AFTER=$PROD_AFTER"
[[ "$PROD_AFTER" == "$PROD_BEFORE" ]] || {
  echo "FS1113_ERROR=PRODUCTION_IMAGE_CHANGED"
  exit 3
}
echo "FS1113_RESULT=PASS"
echo "FS1113_PRODUCTION_DEPLOY=NOT_PERFORMED"
echo "FS1113_PRODUCTION_MUTATION=NONE"
