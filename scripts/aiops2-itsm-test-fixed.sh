#!/usr/bin/env bash
set -uo pipefail

DST=/home/aiops/aiops2-itsm-historical-recovery-20261029
NEW=/home/aiops/aiops2-p0-consolidation
SRC=/home/aiops/aiops2-v2-delivery

echo "=== PREPARATION DU BUNDLE ISOLE ==="

mkdir -p "$DST/app/shared"

if [ ! -f "$DST/app/shared/tenant_scope.py" ]; then
  cp "$NEW/app/shared/tenant_scope.py" \
     "$DST/app/shared/tenant_scope.py"
fi

echo
echo "=== IMAGE PORTAL ==="

IMAGE=$(docker inspect --format '{{.Image}}' \
  aiops2-rebuild-portal) || exit 1

echo "$IMAGE"

echo
echo "=== VERIFICATION FRAMEWORKS ==="

docker run --rm \
  --network none \
  --read-only \
  --tmpfs /tmp:rw,nosuid,size=64m \
  --entrypoint python \
  "$IMAGE" \
  -c '
import importlib.util
for name in ("pytest", "fastapi", "httpx", "requests"):
    print(name, bool(importlib.util.find_spec(name)))
'

echo
echo "=== EXECUTION TESTS UNITAIRES HISTORIQUES ==="

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
  "$IMAGE" \
  -c '
import importlib.util
import subprocess
import sys

if importlib.util.find_spec("pytest") is None:
    print("NON EXECUTE : pytest absent de l image", flush=True)
    sys.exit(20)

tests = [
    "/historical/tests/test_acme_itsm_binding.py",
    "/historical/tests/test_glpi_ticket_read.py",
    "/historical/tests/test_glpi_reader_api.py",
    "/historical/tests/test_hitl_lab.py",
    "/historical/tests/test_acme_hitl_story.py",
    "/historical/tests/test_acme_itsm_correlation.py",
    "/historical/tests/test_hitl_story.py",
    "/historical/tests/test_portal_operator_console.py",
    "/historical/tests/test_portal_operator_read.py",
]

sys.exit(subprocess.call([
    sys.executable, "-m", "pytest",
    "-q", "-p", "no:cacheprovider",
    *tests
]))
'

RESULT=$?

echo
echo "=== BILAN ==="

case "$RESULT" in
  0)
    echo "TESTS : PASS"
    ;;
  20)
    echo "TESTS : NON EXECUTES — pytest absent"
    ;;
  *)
    echo "TESTS : ECHEC OU ENVIRONNEMENT INCOMPLET ($RESULT)"
    ;;
esac

echo
echo "=== SERVICES ACTIFS ==="

for service in core worker portal glpi; do
  docker inspect \
    --format '{{.Name}} : {{.State.Status}}' \
    "aiops2-rebuild-$service" 2>/dev/null || true
done

echo
echo "AUCUN SERVICE REDEMARRÉ"

exit "$RESULT"
