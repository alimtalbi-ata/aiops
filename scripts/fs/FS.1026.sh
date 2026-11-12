#!/usr/bin/env bash
set -Eeuo pipefail
echo '===== FS.1026 | CLEAN-SOURCE TWIN CANDIDATE LIVE DB READ + ASGI HTTP ====='
REPO=/home/aiops/aiops2-v2-delivery
BRANCH=fix/fs-1009-twin-decimal-metrics
IMAGE=aiops2-twin:fs1025-clean-source-candidate-20261106
TWIN=aiops2-rebuild-twin
CORE=aiops2-rebuild-core
EXPECTED_SOURCE_SHA=2cedd1ae5802c82f8d09f7fd7dd78280b3591c48929de4cc16a504487fe59edb
command -v docker >/dev/null
test -d "$REPO/.git"
test "$(docker inspect -f '{{.State.Running}}' "$TWIN")" = true
test "$(docker inspect -f '{{.State.Running}}' "$CORE")" = true
docker image inspect "$IMAGE" >/dev/null
TWIN_BEFORE="$(docker inspect -f '{{.Id}}|{{.Image}}|{{.State.StartedAt}}' "$TWIN")"
CORE_BEFORE="$(docker inspect -f '{{.Id}}|{{.Image}}|{{.State.StartedAt}}' "$CORE")"
test "$(docker run --rm --network none --entrypoint sha256sum "$IMAGE" /app/twin/fs_observations.py | awk '{print $1}')" = "$EXPECTED_SOURCE_SHA"
echo 'CANDIDATE_SOURCE_SHA256=PASS'
TMP="$(mktemp -d /tmp/fs1026.XXXXXXXX)"
chmod 700 "$TMP"
trap 'rm -rf "$TMP"' EXIT
# Read environment only; do not print or persist credentials in Git or reports.
docker inspect --format '{{json .Config.Env}}' "$TWIN" | python3 -c '
import json,sys
with open(sys.argv[1],"w") as out:
 for item in json.load(sys.stdin):
  if "=" not in item: continue
  key,value=item.split("=",1)
  if not key or any(c in key for c in "\n\r= "):continue
  if "\n" in value or "\r" in value:raise SystemExit("multiline env unsupported")
  out.write(key+"="+value+"\n")
' "$TMP/candidate.env"
chmod 600 "$TMP/candidate.env"
echo '===== ISOLATED EPHEMERAL CANDIDATE, READ-ONLY DB QUERY AND IN-PROCESS ASGI ====='
docker run --rm -i --network "container:$TWIN" --env-file "$TMP/candidate.env" --read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 --memory 512m --entrypoint python "$IMAGE" -B - <<'PY'
import asyncio
from decimal import Decimal
from twin.fs_observations import db,NODE_ID,METRIC,THRESHOLD
from twin.main import app
with db() as conn:
 with conn.cursor() as cur:
  cur.execute("""
   SELECT value,observed_at
   FROM aiops.observations
   WHERE node_id=%s AND metric=%s AND payload->>'synthetic'='false'
   ORDER BY observed_at DESC,known_at DESC LIMIT 1
  """,(NODE_ID,METRIC))
  row=cur.fetchone()
assert row is not None,'REAL_OBSERVATION_NOT_FOUND'
value,observed_at=row
assert isinstance(value,Decimal),type(value).__name__
assert value.is_finite() and Decimal(0)<=value<=Decimal(100)
assert observed_at is not None
print('REAL_DB_READ=PASS')
print('REAL_OBSERVATION_TYPE=Decimal')
print('REAL_OBSERVATION_VALUE='+str(value))
async def request(path):
 scope={'type':'http','asgi':{'version':'3.0','spec_version':'2.3'},'http_version':'1.1','method':'GET','scheme':'http','path':path,'raw_path':path.encode(),'query_string':b'','root_path':'','headers':[(b'host',b'fs1026.invalid')],'client':('127.0.0.1',1),'server':('fs1026.invalid',80)}
 messages=[]
 sent=False
 async def receive():
  nonlocal sent
  if not sent:
   sent=True
   return {'type':'http.request','body':b'','more_body':False}
  await asyncio.Event().wait()
 async def send(message):messages.append(message)
 await asyncio.wait_for(app(scope,receive,send),timeout=20)
 starts=[m for m in messages if m.get('type')=='http.response.start']
 assert len(starts)==1,starts
 status=starts[0]['status']
 headers={k.decode('latin-1').lower():v.decode('latin-1') for k,v in starts[0].get('headers',[])}
 body=b''.join(m.get('body',b'') for m in messages if m.get('type')=='http.response.body').decode()
 assert status==200,(path,status,body[:150])
 assert headers.get('content-type','').startswith('text/plain'),(path,headers)
 return body
async def main():
 base=await request('/metrics')
 assert 'aiops_twin_nodes ' in base
 print('CLEAN_SOURCE_BASE_HTTP_METRICS=PASS')
 fs=await request('/api/twin/fs-lab/metrics')
 def one(prefix):
  matches=[line for line in fs.splitlines() if line.startswith(prefix+'{')]
  assert len(matches)==1,(prefix,matches)
  return float(matches[0].split()[-1])
 assert one('aiops_twin_fs_lab_used_percent')==float(value)
 assert one('aiops_twin_fs_lab_alert_firing')==(1 if value>=THRESHOLD else 0)
 assert abs(one('aiops_twin_fs_lab_observation_timestamp_seconds')-observed_at.timestamp())<0.0001
 print('CLEAN_SOURCE_FS_HTTP_METRICS=PASS')
 print('REAL_DB_METRIC_VALUE_MATCH=PASS')
 print('REAL_DB_ALERT_STATE_MATCH=PASS')
 print('REAL_DB_TIMESTAMP_MATCH=PASS')
asyncio.run(main())
print('FS1026_CANDIDATE_E2E=PASS')
PY
test "$(docker inspect -f '{{.Id}}|{{.Image}}|{{.State.StartedAt}}' "$TWIN")" = "$TWIN_BEFORE"
test "$(docker inspect -f '{{.Id}}|{{.Image}}|{{.State.StartedAt}}' "$CORE")" = "$CORE_BEFORE"
echo 'PRODUCTION_RESTARTED=NO'
echo 'PRODUCTION_CONTAINERS_CHANGED=NO'
echo 'DATABASE_WRITES_BY_TEST=0'
echo 'HTTP_WRITES_BY_TEST=0'
echo 'CANDIDATE_HOST_PORT_BOUND=NO'
echo 'FS1026_RESULT=PASS'
