#!/usr/bin/env bash
set -uo pipefail

SRC=/home/aiops/aiops2-v2-delivery
DST=/home/aiops/aiops2-itsm-historical-recovery-20261029
IMAGE=aiops2-itsm-qualification:20261029

echo "=== RECUPERATION DES DEPENDANCES MANQUANTES ==="

FILES=(
  app/portal/operator_read.py
  app/portal/acme-fixtures.json
  app/policy/__init__.py
  app/policy/main.py
)

for file in "${FILES[@]}"; do
  if [ -f "$DST/$file" ]; then
    echo "DEJA PRESENT : $file"
    continue
  fi

  mkdir -p "$DST/$(dirname "$file")"

  commit=$(git -C "$SRC" log --all -1 --format=%H -- "$file")

  if [ -n "$commit" ] &&
     git -C "$SRC" show "$commit:$file" > "$DST/$file" 2>/dev/null; then
    echo "RECUPERE : $file @ ${commit:0:12}"
  else
    rm -f "$DST/$file"
    echo "ABSENT : $file"
  fi
done

echo
echo "=== CONTROLE DES FICHIERS CRITIQUES ==="

for file in \
  app/portal/operator_read.py \
  app/portal/acme-fixtures.json \
  app/policy/main.py
do
  if [ ! -f "$DST/$file" ]; then
    echo "BLOQUANT : $file absent"
    exit 1
  fi
done

echo
echo "=== VALIDATION JSON FIXTURE ==="

python3 - "$DST/app/portal/acme-fixtures.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    json.load(f)

print("FIXTURE JSON : PASS")
PY

echo
echo "=== TESTS HISTORIQUES ==="

docker run --rm \
  --network none \
  --read-only \
  --tmpfs /tmp:rw,nosuid,size=128m \
  -e PYTHONPATH=/historical:/historical/app \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$DST:/historical:ro" \
  --entrypoint python \
  "$IMAGE" \
  -m pytest -q -p no:cacheprovider \
  /historical/tests/test_acme_itsm_binding.py \
  /historical/tests/test_glpi_ticket_read.py \
  /historical/tests/test_glpi_reader_api.py \
  /historical/tests/test_hitl_lab.py \
  /historical/tests/test_acme_hitl_story.py \
  /historical/tests/test_acme_itsm_correlation.py \
  /historical/tests/test_hitl_story.py \
  /historical/tests/test_portal_operator_console.py \
  /historical/tests/test_portal_operator_read.py

RESULT=$?

echo
echo "=== BILAN ==="
echo "CODE_TESTS=$RESULT"

for service in core worker portal glpi n8n; do
  docker inspect \
    --format '{{.Name}} : {{.State.Status}}' \
    "aiops2-rebuild-$service" 2>/dev/null || true
done

exit "$RESULT"
