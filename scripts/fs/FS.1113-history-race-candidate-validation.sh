#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
PROD=aiops2-rebuild-portal
EXPECTED_PROD=aiops2-portal:fs1073-csp-candidate
PROD_BEFORE=""
PROD_ID_BEFORE=""
PROD_IMAGE_ID_BEFORE=""
PROD_TAG_ID_BEFORE=""

# Inspect only: this gate must never deploy or modify the production container.
check_production_on_exit() {
  local gate_status=$?
  trap - EXIT
  if [[ -n "$PROD_BEFORE" ]]; then
    local prod_after
    if ! prod_after="$(docker inspect "$PROD" --format '{{.Config.Image}}')"; then
      echo "FS1113_ERROR=PRODUCTION_POSTCHECK_UNAVAILABLE"
      exit 4
    fi
    echo "FS1113_PRODUCTION_IMAGE_AFTER=$prod_after"
    local prod_id_after prod_image_id_after
    if ! prod_id_after="$(docker inspect "$PROD" --format '{{.Id}}')" || ! prod_image_id_after="$(docker inspect "$PROD" --format '{{.Image}}')"; then
      echo "FS1113_ERROR=PRODUCTION_IDENTITY_POSTCHECK_UNAVAILABLE"
      exit 4
    fi
    if [[ "$prod_id_after" != "$PROD_ID_BEFORE" || "$prod_image_id_after" != "$PROD_IMAGE_ID_BEFORE" ]]; then
      echo "FS1113_ERROR=PRODUCTION_CONTAINER_OR_IMAGE_ID_CHANGED"
      exit 3
    fi
    local prod_tag_id_after
    if ! prod_tag_id_after="$(docker image inspect "$EXPECTED_PROD" --format '{{.Id}}')"; then
      echo "FS1113_ERROR=PRODUCTION_TAG_POSTCHECK_UNAVAILABLE"
      exit 4
    fi
    if [[ "$prod_tag_id_after" != "$PROD_TAG_ID_BEFORE" ]]; then
      echo "FS1113_ERROR=PRODUCTION_TAG_RETARGETED"
      exit 3
    fi
    if [[ "$prod_after" != "$PROD_BEFORE" ]]; then
      echo "FS1113_ERROR=PRODUCTION_IMAGE_CHANGED"
      exit 3
    fi
  fi
  echo "FS1113_PRODUCTION_DEPLOY=NOT_PERFORMED"
  echo "FS1113_PRODUCTION_MUTATION=NONE_BY_THIS_SCRIPT"
  if (( gate_status == 0 )); then
    echo "FS1113_RESULT=PASS"
  else
    echo "FS1113_RESULT=FAIL"
  fi
  exit "$gate_status"
}
trap check_production_on_exit EXIT

echo "FS1113_MODE=NONPRODUCTION_HISTORY_RACE_FIX_BUILD_AND_FULL_BROWSER_GATE"
PROD_BEFORE="$(docker inspect "$PROD" --format '{{.Config.Image}}')"
echo "FS1113_PRODUCTION_IMAGE_BEFORE=$PROD_BEFORE"
PROD_ID_BEFORE="$(docker inspect "$PROD" --format '{{.Id}}')"
PROD_IMAGE_ID_BEFORE="$(docker inspect "$PROD" --format '{{.Image}}')"
[[ "$PROD_BEFORE" == "$EXPECTED_PROD" ]] || {
  echo "FS1113_ERROR=UNEXPECTED_PRODUCTION_IMAGE"
  exit 2
}
PROD_TAG_ID_BEFORE="$(docker image inspect "$EXPECTED_PROD" --format '{{.Id}}')" || {
  echo "FS1113_ERROR=PRODUCTION_TAG_PREFLIGHT_UNAVAILABLE"
  exit 4
}
[[ "$PROD_TAG_ID_BEFORE" == "$PROD_IMAGE_ID_BEFORE" ]] || {
  echo "FS1113_ERROR=PRODUCTION_TAG_CONTAINER_MISMATCH"
  exit 2
}

# Always rebuild from current checkout; never trust a cached candidate tag.
bash "$ROOT/scripts/fs/FS.1097-build-history-chart-candidate.sh"

# Fail closed after candidate build, before starting browser/network qualification.
PROD_TAG_ID_AFTER_BUILD="$(docker image inspect "$EXPECTED_PROD" --format '{{.Id}}')" || {
  echo "FS1113_ERROR=PRODUCTION_TAG_POSTBUILD_UNAVAILABLE"
  exit 4
}
if [[ "$PROD_TAG_ID_AFTER_BUILD" != "$PROD_TAG_ID_BEFORE" ]]; then
  echo "FS1113_ERROR=PRODUCTION_TAG_RETARGETED_DURING_BUILD"
  exit 3
fi
PROD_ID_AFTER_BUILD="$(docker inspect "$PROD" --format '{{.Id}}')" || exit 4
PROD_IMAGE_ID_AFTER_BUILD="$(docker inspect "$PROD" --format '{{.Image}}')" || exit 4
if [[ "$PROD_ID_AFTER_BUILD" != "$PROD_ID_BEFORE" || "$PROD_IMAGE_ID_AFTER_BUILD" != "$PROD_IMAGE_ID_BEFORE" ]]; then
  echo "FS1113_ERROR=PRODUCTION_CHANGED_DURING_BUILD"
  exit 3
fi

# Reuse publish-first rootless network lifecycle and full Chromium matrix.
bash "$ROOT/scripts/fs/FS.1107-full-history-candidate-external-first-browser.sh"
