#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
echo "FS1135_MODE=READ_ONLY_REAL_CORE_POSTGRES_RECONCILIATION"
echo "FS1135_PRODUCTION_MUTATION=NONE"
echo "FS1135_PORTAL_7777_MUTATION=NONE"
test -f "$ROOT/scripts/fs/fs1135_readonly_reconcile.py"
python3 -m py_compile "$ROOT/scripts/fs/fs1135_readonly_reconcile.py"
docker inspect aiops2-rebuild-core --format '{{.State.Running}}' | grep -qx true
docker exec -i aiops2-rebuild-core python - < "$ROOT/scripts/fs/fs1135_readonly_reconcile.py"
echo "FS1135_FINAL_STATUS=PASS"
