#!/usr/bin/env bash
set -uo pipefail

DST=/home/aiops/aiops2-itsm-historical-recovery-20261029
NEW=/home/aiops/aiops2-p0-consolidation
BASE=$(docker inspect --format '{{.Image}}' aiops2-rebuild-portal) || exit 1
TAG=aiops2-itsm-qualification:20261029
BUILD=$(mktemp -d) || exit 1
trap 'rm -rf "$BUILD"' EXIT

echo "=== CONSTRUCTION IMAGE DE QUALIFICATION ==="

cat > "$BUILD/Dockerfile" <<EOF
FROM $BASE
USER root
RUN python -m pip install --no-cache-dir pytest httpx
EOF

if ! docker build -q -t "$TAG" "$BUILD"; then
  echo "ECHEC CONSTRUCTION : aucune modification de production"
  exit 1
fi

echo
echo "=== TESTS UNITAIRES HISTORIQUES ==="

docker run --rm \
  --network none \
  --read-only \
  --tmpfs /tmp:rw,nosuid,size=128m \
  --tmpfs /root/.cache:rw,nosuid,size=32m \
  -e PYTHONPATH=/historical/app \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$DST/app:/historical/app:ro" \
  -v "$DST/tests:/historical/tests:ro" \
  --entrypoint python \
  "$TAG" \
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
echo "=== RESULTAT ==="
echo "CODE_TESTS=$RESULT"

echo
echo "=== PRODUCTION ==="
for service in core worker portal glpi n8n; do
  docker inspect \
    --format '{{.Name}} : {{.State.Status}}' \
    "aiops2-rebuild-$service" 2>/dev/null || true
done

exit "$RESULT"
