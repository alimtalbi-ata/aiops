#!/usr/bin/env bash
set -uo pipefail

SRC=/home/aiops/aiops2-v2-delivery
DST=/home/aiops/aiops2-itsm-historical-recovery-20261029
IMAGE=aiops2-itsm-qualification:20261029

echo "=== RECUPERATION DU SCENARIO HITL ==="

file=demo/hitl_golden_demo.py
mkdir -p "$DST/demo"

if [ ! -f "$DST/$file" ]; then
  commit=$(git -C "$SRC" log --all -1 --format=%H -- "$file")
  if [ -z "$commit" ] ||
     ! git -C "$SRC" show "$commit:$file" > "$DST/$file"; then
    echo "ERREUR : scenario HITL introuvable"
    exit 1
  fi
  echo "RECUPERE : $file @ ${commit:0:12}"
else
  echo "DEJA PRESENT : $file"
fi

echo
echo "=== TESTS PYTHON PAR GROUPES ==="

run_group() {
  local label="$1"
  shift

  echo
  echo "--- $label ---"

  docker run --rm \
    --network none \
    --read-only \
    --tmpfs /tmp:rw,nosuid,size=128m \
    -e PYTHONPATH=/historical:/historical/app \
    -e PYTHONDONTWRITEBYTECODE=1 \
    -v "$DST:/historical:ro" \
    --entrypoint python \
    "$IMAGE" \
    -m pytest -q -p no:cacheprovider "$@"

  local result=$?
  echo "RESULTAT $label : $result"
  return "$result"
}

failures=0

run_group "GLPI" \
  /historical/tests/test_glpi_ticket_read.py \
  /historical/tests/test_glpi_reader_api.py \
  || failures=$((failures+1))

run_group "ITSM" \
  /historical/tests/test_acme_itsm_binding.py \
  /historical/tests/test_acme_itsm_correlation.py \
  || failures=$((failures+1))

run_group "HITL" \
  /historical/tests/test_hitl_lab.py \
  /historical/tests/test_hitl_story.py \
  /historical/tests/test_acme_hitl_story.py \
  || failures=$((failures+1))

run_group "CONSOLE" \
  /historical/tests/test_portal_operator_console.py \
  /historical/tests/test_portal_operator_read.py \
  || failures=$((failures+1))

echo
echo "=== SYNTHESE ==="
echo "GROUPES_EN_ECHEC=$failures"

echo
echo "=== SERVICES ACTIFS ==="

for service in core worker portal glpi n8n; do
  docker inspect \
    --format '{{.Name}} : {{.State.Status}}' \
    "aiops2-rebuild-$service" 2>/dev/null || true
done

if [ "$failures" -eq 0 ]; then
  echo "QUALIFICATION PYTHON : PASS"
else
  echo "QUALIFICATION PYTHON : INCOMPLETE"
fi

exit "$((failures > 0))"
