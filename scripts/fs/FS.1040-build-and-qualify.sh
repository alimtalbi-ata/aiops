#!/usr/bin/env bash
# Local image build and isolated qualification. Does not start or replace production container.
set -euo pipefail
ROOT="${1:-.}"
IMAGE="aiops2-portal:fs1040-sql-guard-candidate"
echo "FS1040_MODE=LOCAL_CANDIDATE_ONLY"
docker build --network none -f "$ROOT/scripts/fs/Dockerfile.fs1040" -t "$IMAGE" "$ROOT"
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --env PYTHONDONTWRITEBYTECODE=1 --entrypoint python "$IMAGE" -c '
import hashlib, inspect
import portal.explorer_api as m
from fastapi import HTTPException
print("FS1040_PATCHED_MODULE_SHA256="+hashlib.sha256(inspect.getsource(m).encode()).hexdigest())
cases=[
 ("basic","SELECT 1",True),
 ("table","SELECT id FROM public.example LIMIT 2",True),
 ("insert","INSERT INTO example VALUES (1)",False),
 ("update","UPDATE example SET id=1",False),
 ("delete","DELETE FROM example",False),
 ("drop","DROP TABLE example",False),
 ("truncate","TRUNCATE example",False),
 ("multiple","SELECT 1; DELETE FROM example",False),
 ("comment","SELECT 1 /*x*/",False),
 ("cte_write","WITH x AS (DELETE FROM example RETURNING id) SELECT * FROM x",False),
 ("select_into","SELECT 1 INTO TEMP TABLE example",False),
 ("select_into_plain","SELECT id INTO example FROM source",False),
 ("for_update","SELECT * FROM example FOR UPDATE",False),
 ("for_share","SELECT * FROM example FOR SHARE",False),
 ("sleep","SELECT pg_sleep(1)",False),
 ("dblink","SELECT dblink(\x27x\x27,\x27y\x27)",False),
 ("null","SELECT NULL",True),
]
failed=0
for name,sql,expected in cases:
 try: m._safe_query(sql); actual=True
 except HTTPException: actual=False
 ok=actual==expected
 print("CASE=%s RESULT=%s"%(name,"PASS" if ok else "FAIL"))
 failed+=not ok
print("FS1040_CASES=%s FAILURES=%s"%(len(cases),failed))
print("FS1040_SQL_GUARD="+("PASS" if not failed else "FAIL"))
raise SystemExit(bool(failed))
'
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --env PYTHONDONTWRITEBYTECODE=1 --entrypoint python "$IMAGE" -c '
import json
from portal.main import app
routes={getattr(r,"path","") for r in app.routes}
required={"/health","/explorer/{page}","/api/explorer/catalog"}
missing=sorted(required-routes)
print("FS1040_ROUTE_COUNT="+str(len(routes)))
print("FS1040_MISSING_ROUTES="+json.dumps(missing))
print("FS1040_ROUTES="+("PASS" if not missing else "FAIL"))
raise SystemExit(bool(missing))
'
echo "FS1040_CANDIDATE=PASS"
