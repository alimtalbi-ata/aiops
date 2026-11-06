#!/usr/bin/env bash
# FS.1039 — Validate candidate guard against exact deployed explorer module in isolated container.
# No source export, DB connection, HTTP call, production change or image rebuild.
set -euo pipefail
ROOT="${1:-.}"
IMAGE="${FS1039_PORTAL_IMAGE:-aiops2-portal:fs621-explorers-candidate}"
echo "FS1039_MODE=ISOLATED_INTEGRATION"
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --mount "type=bind,src=$(realpath "$ROOT/app/portal/sql_readonly_guard.py"),dst=/candidate/sql_readonly_guard.py,readonly" \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --entrypoint python "$IMAGE" -c '
import ast, hashlib, inspect, sys
from fastapi import HTTPException
import portal.explorer_api as explorer
sys.path.insert(0,"/candidate")
from sql_readonly_guard import validate_select
module_hash=hashlib.sha256(inspect.getsource(explorer).encode()).hexdigest()
print("EXPLORER_SHA256="+module_hash)
expected="222439c2b81877d1cb5925f817263270629985d1de41e38be8db72ee7f2b9dc4"
if module_hash!=expected:
 print("FS1039_SOURCE_PARITY=FAIL")
 raise SystemExit(2)
print("FS1039_SOURCE_PARITY=PASS")
def candidate_safe_query(sql):
 try: return validate_select(sql)
 except ValueError: raise HTTPException(400,"only_single_select_allowed")
explorer._safe_query=candidate_safe_query
tests=[
 ("select_basic","SELECT 1",True),
 ("select_table","SELECT id FROM public.example LIMIT 2",True),
 ("insert","INSERT INTO example VALUES (1)",False),
 ("update","UPDATE example SET id=1",False),
 ("delete","DELETE FROM example",False),
 ("drop","DROP TABLE example",False),
 ("truncate","TRUNCATE example",False),
 ("multi","SELECT 1; DELETE FROM example",False),
 ("comment","SELECT 1 /*x*/",False),
 ("cte_write","WITH x AS (DELETE FROM example RETURNING id) SELECT * FROM x",False),
 ("select_into","SELECT 1 INTO TEMP TABLE example",False),
 ("select_into_plain","SELECT id INTO example FROM source",False),
 ("for_update","SELECT * FROM example FOR UPDATE",False),
 ("for_share","SELECT * FROM example FOR SHARE",False),
 ("pg_sleep","SELECT pg_sleep(1)",False),
 ("dblink","SELECT dblink(\x27x\x27,\x27y\x27)",False),
 ("select_null","SELECT NULL",True),
]
fail=0
for name,sql,expect in tests:
 try: explorer._safe_query(sql); allowed=True
 except HTTPException: allowed=False
 ok=allowed==expect
 print("CASE=%s RESULT=%s"%(name,"PASS" if ok else "FAIL"))
 fail+=not ok
print("FS1039_CASES=%s FAILURES=%s"%(len(tests),fail))
print("FS1039_INTEGRATION="+("PASS" if not fail else "FAIL"))
raise SystemExit(bool(fail))
'
