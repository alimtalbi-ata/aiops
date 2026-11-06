#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.995 | FS994 DEMO RUN READ-ONLY FORENSICS ====='
docker exec aiops2-e2e-v1-aiops2-core-1 python - <<'PY'
import json,os,urllib.request
rid='RUN-171493F5FE80D45E'
token=os.getenv('AIOPS_INTERNAL_TOKEN') or os.getenv('ADMIN_TOKEN')
assert token,'Core internal token unavailable'
req=urllib.request.Request('http://127.0.0.1:810/api/runs/'+rid,headers={'Authorization':'Bearer '+token})
with urllib.request.urlopen(req,timeout=15) as r:detail=json.load(r)
run=detail['run']
assert run['run_id']==rid
print('RUN_ID='+rid)
print('MODE='+str(run['mode']))
print('SCENARIO='+str(run['scenario_id']))
print('CORE_STATUS='+str(run['status']))
events=detail.get('events',[])
for e in events:
 stage=e.get('stage')
 if stage in ('DGX_ANALYST','DGX_CRITIC','POLICY','HITL','REMEDIATE','VERIFY','RECONCILE','LEARN'):
  p=e.get('payload') or {}
  if not isinstance(p,dict):p={}
  fields={}
  for k in ('decision','state','reason','validated','preconditions_verified','fencing_verified','human_approved','synthetic','executor','attempt'):
   if k in p and isinstance(p[k],(str,bool,int,float,type(None))):fields[k]=p[k]
  for k in ('analysis','critique'):
   x=p.get(k)
   if isinstance(x,dict):fields[k]={z:x[z] for z in ('validated','diagnostic_confidence','confidence','severity','decision') if z in x and isinstance(x[z],(str,bool,int,float,type(None)))}
  print('EVENT='+json.dumps({'sequence':e.get('sequence'),'stage':stage,'type':e.get('event_type'),'status':e.get('status'),'decision':e.get('decision'),'fields':fields},default=str,sort_keys=True))
for g in detail.get('gates',[]):
 print('GATE='+json.dumps({k:g.get(k) for k in ('stage','state','decision','reason')},default=str,sort_keys=True))
print('REMEDIATE_EVENT_COUNT='+str(sum(e.get('stage')=='REMEDIATE' for e in events)))
print('VERIFY_EVENT_COUNT='+str(sum(e.get('stage')=='VERIFY' for e in events)))
print('FORENSIC_READ_ONLY=PASS')
PY
echo 'HTTP_WRITES=0'
echo 'NEW_WORKFLOWS_STARTED=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.995 ====='
