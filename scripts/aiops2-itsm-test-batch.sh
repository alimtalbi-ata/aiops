#!/usr/bin/env bash
set -uo pipefail

DST=/home/aiops/aiops2-itsm-historical-recovery-20261029
NEW=/home/aiops/aiops2-p0-consolidation

echo "=== IMAGE PORTAL ACTUELLE ==="
IMAGE=$(docker inspect --format '{{.Image}}' aiops2-rebuild-portal)
echo "IMAGE : $IMAGE"

echo
echo "=== TESTS HISTORIQUES EN CONTENEUR ISOLE ==="

docker run --rm \
  --network none \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  -v "$DST/app:/historical/app:ro" \
  -v "$DST/tests:/historical/tests:ro" \
  -v "$NEW/app/shared/tenant_scope.py:/historical/app/shared/tenant_scope.py:ro" \
  --entrypoint python \
  "$IMAGE" \
  -c '
import pathlib
import sys
import unittest

sys.path.insert(0, "/historical/app")
sys.path.insert(0, "/historical")

suite = unittest.defaultTestLoader.discover(
    "/historical/tests",
    pattern="test_*.py",
    top_level_dir="/historical",
)
print("CAS CHARGES :", suite.countTestCases(), flush=True)
result = unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(0 if result.wasSuccessful() and suite.countTestCases() else 1)
'

echo
echo "=== TEST JAVASCRIPT CONSOLE ==="

if command -v node >/dev/null 2>&1; then
  node --test "$DST/tests/test_portal_operator_console.mjs"
else
  echo "NODE ABSENT SUR HOTE : test JS non execute"
fi

echo
echo "=== SERVICES DE PRODUCTION INCHANGES ==="

for service in core worker portal glpi; do
  docker inspect --format \
    '{{.Name}} : {{.State.Status}}' \
    "aiops2-rebuild-$service"
done
