#!/usr/bin/env bash
set -Eeuo pipefail
echo '===== FS.1017 | CORE ISOLATED IMAGE BUILD AND ASGI METRICS CONTRACT ====='
REPO=/home/aiops/aiops2-v2-delivery
REF=c971e39d042dc805ac4ec0d6fbe4844248a4a1c5
IMAGE=aiops2-core:fs1017-metrics-candidate-20261106
CORE=aiops2-rebuild-core
BASE_ID=sha256:a41a250997460793b50b7eb5a5c41a637d1e39960ceb7e9664d2e1553bf784a7
test -d "$REPO/.git" || { echo 'NO_GO=REPO_NOT_FOUND'; exit 1; }
git -C "$REPO" cat-file -e "$REF^{commit}"
test "$(docker inspect --format '{{.Image}}' "$CORE")" = "$BASE_ID" || { echo 'NO_GO=LIVE_CORE_IMAGE_CHANGED'; exit 1; }
test "$(docker inspect --format '{{.State.Running}}' "$CORE")" = true || { echo 'NO_GO=LIVE_CORE_NOT_RUNNING'; exit 1; }
docker image inspect "$BASE_ID" >/dev/null
TMP="$(mktemp -d /tmp/fs1017.XXXXXXXX)"
chmod 700 "$TMP"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/context"
git -C "$REPO" archive "$REF" app/core app/shared app/requirements.txt | tar -xf - -C "$TMP/context"
python3 - "$TMP/context/app/core/main.py" <<'PY'
import ast,sys
p=sys.argv[1]
s=open(p).read()
t=ast.parse(s)
assert any(isinstance(n,ast.ImportFrom) and n.module=="fastapi.responses" and any(a.name=="PlainTextResponse" for a in n.names) for n in t.body)
matches=[n for n in t.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=="metrics"]
assert len(matches)==1
decorators=matches[0].decorator_list
assert any(isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr=="get" and d.args and isinstance(d.args[0],ast.Constant) and d.args[0].value=="/metrics" and any(k.arg=="response_class" and isinstance(k.value,ast.Name) and k.value.id=="PlainTextResponse" for k in d.keywords) for d in decorators)
print("CORE_SOURCE_METRICS_CONTRACT=PASS")
PY
echo '===== BUILD ISOLATED CANDIDATE (NO PRODUCTION CONTAINER CHANGES) ====='
docker build --pull=false -f "$TMP/context/app/core/Dockerfile" -t "$IMAGE" "$TMP/context/app"
echo '===== TEST CANDIDATE ASGI RESPONSE, NO DATABASE CONNECTION ====='
docker run --rm -i --network none -e AIOPS_INTERNAL_TOKEN=fs1017-isolated-test-only --entrypoint python "$IMAGE" -B - <<'PY'
import asyncio
from contextlib import contextmanager
import core.main as m
@contextmanager
def fake_db():
 class Conn:
  def execute(self,sql):
   assert "from aiops.runs" in sql.lower()
   return self
  def fetchone(self):
   return (12,3,2,7)
 yield Conn()
m.db=fake_db
async def check():
 scope={"type":"http","asgi":{"version":"3.0"},"http_version":"1.1","method":"GET","scheme":"http","path":"/metrics","raw_path":b"/metrics","query_string":b"","root_path":"","headers":[],"client":("127.0.0.1",1),"server":("127.0.0.1",810)}
 sent=[]
 async def receive():return {"type":"http.request","body":b"","more_body":False}
 async def send(msg):sent.append(msg)
 await m.app(scope,receive,send)
 start=next(x for x in sent if x["type"]=="http.response.start")
 body=b"".join(x.get("body",b"") for x in sent if x["type"]=="http.response.body")
 headers={k.lower():v for k,v in start["headers"]}
 assert start["status"]==200,start
 ct=headers[b"content-type"].decode()
 assert ct.startswith("text/plain"),ct
 assert "version=0.0.4" not in ct or "text/plain" in ct
 assert body==b"aiops_runs_total 12\naiops_runs_running 3\naiops_runs_blocked 2\naiops_runs_resolved 7\n",body
 print("CORE_ASGI_HTTP=200")
 print("CORE_ASGI_CONTENT_TYPE="+ct)
 print("CORE_ASGI_METRICS_BODY=PASS")
asyncio.run(check())
PY
echo '===== VERIFY PRODUCTION UNCHANGED ====='
test "$(docker inspect --format '{{.Image}}' "$CORE")" = "$BASE_ID"
test "$(docker inspect --format '{{.State.Running}}' "$CORE")" = true
echo "CANDIDATE_IMAGE=$IMAGE"
echo 'PRODUCTION_CORE_IMAGE_UNCHANGED=YES'
echo 'PRODUCTION_RESTARTED=NO'
echo 'DATABASE_WRITES=0'
echo 'HTTP_WRITES=0'
echo 'FS1017_RESULT=CANDIDATE_PASS_CUTOVER_NOT_AUTHORIZED'
echo '===== END FS.1017 ====='
