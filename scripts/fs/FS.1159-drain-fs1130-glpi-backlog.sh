#!/usr/bin/env bash
# FS1159: bounded real FS1130 backlog drain; stop on any ambiguous outbox state.
set -euo pipefail
umask 077
echo "FS1159_MODE=REAL_FS1130_BACKLOG_DRAIN"
echo "FS1159_PORTAL_MUTATION=NONE"
echo "FS1159_MAX_NEW_TICKETS=41"
test -f app/core/glpi_client.py && test -f scripts/fs/fs1136_glpi_outbox.py
TOKEN_FILE="$HOME/.config/aiops2/glpi-core/fs1150-app-token"
test -s "$TOKEN_FILE"
docker cp app/core/glpi_client.py aiops2-rebuild-core:/tmp/fs1159_glpi_client.py >/dev/null
docker cp scripts/fs/fs1136_glpi_outbox.py aiops2-rebuild-core:/tmp/fs1159_outbox.py >/dev/null
# Portal environment is read-only; secret material travels via stdin, never command args.
{ cat "$TOKEN_FILE"; docker exec aiops2-rebuild-portal python -c 'import os,sys;sys.stdout.write(os.environ["GLPI_USER_TOKEN"]+"\n")'; } |
docker exec -i aiops2-rebuild-core python -c '
import os,sys,importlib.util
app=sys.stdin.readline().strip();user=sys.stdin.readline().strip()
if not (len(app)==64 and user):sys.exit("FS1159_CREDENTIALS_MISSING")
os.environ.update(AIOPS_GLPI_URL="http://aiops2-rebuild-glpi/apirest.php",AIOPS_GLPI_APP_TOKEN=app,AIOPS_GLPI_USER_TOKEN=user)
spec=importlib.util.spec_from_file_location("core.glpi_client","/tmp/fs1159_glpi_client.py")
module=importlib.util.module_from_spec(spec);sys.modules["core.glpi_client"]=module;spec.loader.exec_module(module)
spec2=importlib.util.spec_from_file_location("fs1159_outbox","/tmp/fs1159_outbox.py")
outbox=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(outbox)
from shared.db import db
def counts():
 with db() as c:
  exists=c.execute("select to_regclass(%s)",("aiops.glpi_ticket_links",)).fetchone()[0]
  if not exists:raise RuntimeError("FS1159_OUTBOX_ABSENT")
  return dict(c.execute("""select state,count(*) from aiops.glpi_ticket_links
    where incident_id in (select incident_id from aiops.incidents where external_id like %s)
    group by state""",("FS1130-%",)).fetchall())
before=counts()
print("FS1159_BEFORE="+str(before),flush=True)
if any(before.get(x,0) for x in ("UNKNOWN","CLAIMED","ERROR")):
 sys.exit("FS1159_STOP_AMBIGUOUS_STATE_RECONCILE")
if before.get("CONFIRMED",0)<1:sys.exit("FS1159_STOP_CANARY_NOT_CONFIRMED")
max_new=min(41,before.get("PENDING",0))
for i in range(max_new):
 pre=counts()
 if any(pre.get(x,0) for x in ("UNKNOWN","CLAIMED","ERROR")):
  sys.exit("FS1159_STOP_AMBIGUOUS_STATE_RECONCILE")
 if pre.get("PENDING",0)==0:break
 outbox.sync(1)
 post=counts()
 if any(post.get(x,0) for x in ("UNKNOWN","CLAIMED","ERROR")):
  sys.exit("FS1159_STOP_AMBIGUOUS_STATE_RECONCILE")
 if post.get("CONFIRMED",0)!=pre.get("CONFIRMED",0)+1:
  sys.exit("FS1159_STOP_NO_CONFIRMED_PROGRESS")
 print("FS1159_PROGRESS="+str(i+1)+"/"+str(max_new),flush=True)
print("FS1159_AFTER="+str(counts()),flush=True)
'
echo "FS1159_FINAL_STATUS=BACKLOG_DRAIN_COMPLETED_REVIEW_COUNTS"
