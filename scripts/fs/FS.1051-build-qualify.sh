#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
echo "FS1051_MODE=LOCAL_CANDIDATE_ONLY"
docker image inspect aiops2-portal:fs1040-sql-guard-candidate >/dev/null
python3 - <<'PY'
import ast
from pathlib import Path
for name in ("app/portal/fs1051_visual.py","scripts/fs/fs1051_register.py"):
 ast.parse(Path(name).read_text())
print("FS1051_AST=PASS")
PY
docker build -f scripts/fs/Dockerfile.fs1051 -t aiops2-portal:fs1051-visual-candidate .
docker run --rm -i --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
 -e PYTHONDONTWRITEBYTECODE=1 -e AIOPS_INTERNAL_TOKEN=fs1051-dummy \
 -e EXPLORER_ENABLED=1 -e EXPLORER_ALLOWED_CIDRS=127.0.0.1/32 \
 --entrypoint python aiops2-portal:fs1051-visual-candidate - <<'PY'
from portal.main import app
routes={getattr(r,"path","") for r in app.routes}
required={"/health","/explorer/databases","/explorer/prometheus","/explorer/cmdb","/api/explorer/catalog","/explorer/visual","/api/fs1051/prometheus","/api/fs1051/twin"}
missing=sorted(required-routes)
print("FS1051_ROUTE_COUNT="+str(len(routes)))
print("FS1051_MISSING_ROUTES="+str(missing))
assert not missing
from portal.fs1051_visual import router
assert len(router.routes)==3
print("FS1051_ROUTES=PASS")
PY
echo "FS1051_CANDIDATE=PASS"
