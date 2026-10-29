#!/usr/bin/env bash
set -uo pipefail

DST=/home/aiops/aiops2-itsm-historical-recovery-20261029
BASE_ID=$(docker inspect --format '{{.Image}}' aiops2-rebuild-portal) || exit 1
BASE_TAG=aiops2-portal-qualification-base:local
TEST_TAG=aiops2-itsm-qualification:20261029

BUILD=$(mktemp -d) || exit 1
trap 'rm -rf "$BUILD"' EXIT

echo "=== IMAGE LOCALE ==="

docker image inspect "$BASE_ID" >/dev/null || exit 1
docker tag "$BASE_ID" "$BASE_TAG" || exit 1

echo "Image locale : $BASE_TAG"

echo
echo "=== CONSTRUCTION ENVIRONNEMENT TEST ==="

cat > "$BUILD/Dockerfile" <<EOF
FROM $BASE_TAG
USER root
RUN python -m pip install --no-cache-dir pytest httpx
EOF

if ! docker build --pull=false -t "$TEST_TAG" "$BUILD"; then
  echo "ECHEC : environnement de test non construit"
  echo "Aucun conteneur de production modifie"
  exit 1
fi

echo
echo "=== TESTS HISTORIQUES ==="

docker run --rm \
  --network none \
  --read-only \
  --tmpfs /tmp:rw,nosuid,size=128m \
  -e PYTHONPATH=/historical/app \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$DST/app:/historical/app:ro" \
  -v "$DST/tests:/historical/tests:ro" \
  --entrypoint python \
  "$TEST_TAG" \
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
echo "=== RESULTAT TESTS : $RESULT ==="

echo
echo "=== SERVICES PRODUCTION ==="

for service in core worker portal glpi n8n; do
  docker inspect \
    --format '{{.Name}} : {{.State.Status}}' \
    "aiops2-rebuild-$service" 2>/dev/null || true
done

exit "$RESULT"
