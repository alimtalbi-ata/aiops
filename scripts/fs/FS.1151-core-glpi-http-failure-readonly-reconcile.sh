#!/usr/bin/env bash
# FS1151: read-only reconciliation after FS1150 HTTP error. No new GLPI ticket.
set -euo pipefail
echo "FS1151_MODE=READ_ONLY_CORE_GLPI_FAILURE_RECONCILIATION"
echo "FS1151_MUTATION=NONE"
echo "FS1151_PORTAL_MUTATION=NONE"
docker exec -i aiops2-rebuild-core python - <<'PY'
import os,json,psycopg
def emit(**x):print(json.dumps(x,sort_keys=True,default=str),flush=True)
with psycopg.connect(os.environ['DATABASE_URL']) as c:
 with c.cursor() as cur:
  exists=cur.execute("select to_regclass('aiops.glpi_ticket_links')").fetchone()[0]
  emit(type='outbox',exists=bool(exists))
  if exists:
   rows=cur.execute("""select l.state,count(*) from aiops.glpi_ticket_links l
    join aiops.incidents i on i.incident_id=l.incident_id
    where i.external_id like 'FS1130-%' group by l.state order by l.state""").fetchall()
   emit(type='outbox_states',states=dict(rows))
   sample=cur.execute("""select l.incident_id,l.state,l.glpi_ticket_id,l.attempts,l.last_error
    from aiops.glpi_ticket_links l join aiops.incidents i on i.incident_id=l.incident_id
    where i.external_id like 'FS1130-%' and l.state<>'PENDING'
    order by l.claimed_at desc nulls last limit 5""").fetchall()
   for iid,state,tid,attempts,error in sample:
    emit(type='outbox_nonpending',incident_id=iid,state=state,ticket_id=tid,attempts=attempts,
     error_code=error if error and error.startswith('GLPI_API_') else None)
PY
# Verify API session using dedicated app token from local protected file and existing
# user token read-only from Portal. Never print either secret.
TOKEN_FILE="$HOME/.config/aiops2/glpi-core/fs1150-app-token"
test -s "$TOKEN_FILE" || { echo "FS1151_ERROR=APP_TOKEN_FILE_MISSING";exit 2; }
{ cat "$TOKEN_FILE"; printf '\n'; docker exec aiops2-rebuild-portal python -c 'import os,sys;sys.stdout.write(os.getenv("GLPI_USER_TOKEN","")+"\\n")'; printf '\n'; } |
docker exec -i aiops2-rebuild-core python -c '
import os,sys,json,urllib.request,urllib.error
app=sys.stdin.readline().strip();user=sys.stdin.readline().strip()
if not (app and user):
 print(json.dumps({"type":"glpi_init_session","result":"CREDENTIAL_TRANSFER_MISSING","app_present":bool(app),"user_present":bool(user),"secret_values_exposed":False}));sys.exit(3)
url="http://aiops2-rebuild-glpi/apirest.php/initSession"
req=urllib.request.Request(url,headers={"App-Token":app,"Authorization":"user_token "+user})
try:
 with urllib.request.urlopen(req,timeout=12) as response:
  obj=json.loads(response.read(8192))
  token=obj.get("session_token")
  print(json.dumps({"type":"glpi_init_session","http_status":response.status,
   "session_established":bool(token),"secret_values_exposed":False}))
  if token:
   close=urllib.request.Request("http://aiops2-rebuild-glpi/apirest.php/killSession",
     headers={"App-Token":app,"Session-Token":token})
   with urllib.request.urlopen(close,timeout=12) as r:
    print(json.dumps({"type":"glpi_session_close","http_status":r.status}))
except urllib.error.HTTPError as e:
 raw=e.read(4096)
 try:
  payload=json.loads(raw)
  code=payload[0] if isinstance(payload,list) and payload and isinstance(payload[0],str) else None
 except Exception:code=None
 print(json.dumps({"type":"glpi_init_session","http_status":e.code,
   "glpi_error_code":code,"secret_values_exposed":False}))
except Exception as e:
 print(json.dumps({"type":"glpi_init_session","error_type":type(e).__name__,
   "secret_values_exposed":False}))
'
echo "FS1151_FINAL_STATUS=READ_ONLY_COMPLETE"
