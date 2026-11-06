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
new={"/explorer/visual","/api/fs1051/prometheus","/api/fs1051/twin"}
missing=sorted(new-routes)
print("FS1051_ROUTE_COUNT="+str(len(routes)))
print("FS1051_NEW_ROUTES_MISSING="+str(missing))
assert not missing, "new FS1051 routes missing"
from portal.fs1051_visual import router
assert len(router.routes)==3
print("FS1051_NEW_ROUTES=PASS")
# Legacy explorer routes may be registered by a catch-all dispatcher rather than
# as individual FastAPI paths. Test their ASGI behavior rather than raw path strings.
import asyncio
async def probe(path):
 sent=[]
 async def receive():return {"type":"http.request","body":b"","more_body":False}
 async def send(msg):sent.append(msg)
 scope={"type":"http","asgi":{"version":"3.0"},"http_version":"1.1",
        "method":"GET","scheme":"http","path":path,"raw_path":path.encode(),
        "root_path":"","query_string":b"","headers":[(b"host",b"localhost")],
        "client":("127.0.0.1",12345),"server":("localhost",80)}
 await app(scope,receive,send)
 return next((m["status"] for m in sent if m["type"]=="http.response.start"),None)
async def check():
 for path in ("/health","/explorer/databases","/explorer/prometheus","/explorer/cmdb","/api/explorer/catalog","/explorer/visual"):
  status=await probe(path)
  print("FS1051_ASGI="+path+" STATUS="+str(status))
  assert status==200, (path,status)
asyncio.run(check())
print("FS1051_LEGACY_AND_NEW_ASGI=PASS")
PY
echo "FS1051_CANDIDATE=PASS"
