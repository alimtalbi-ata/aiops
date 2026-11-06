#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.996 | DEMO SIMULATION SEMANTICS / NO LIVE REMEDIATION ====='
SOURCE=/home/aiops/aiops2-fs-demo-source/integration/worker-fs-candidate/main.py
EXPECTED=7bca86f061b371fc1b03f1a8f7c693364a6155355be4de8eaa928561e2a4fc3b
echo "$EXPECTED  $SOURCE" | sha256sum -c -
echo '===== SOURCE EXECUTION BRANCHES ====='
python3 - "$SOURCE" <<'PY'
import ast,pathlib,sys
s=pathlib.Path(sys.argv[1]).read_text();t=ast.parse(s)
f=next(n for n in ast.walk(t) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=='_execute_stage_blocking')
print('FUNCTION='+f.name)
for n in ast.walk(f):
 if isinstance(n,ast.If):
  cond=ast.get_source_segment(s,n.test) or ''
  if any(x in cond for x in ('REMEDIATE','VERIFY','HITL','POLICY','LIVE','synthetic')):
   print('CONDITION_LINE='+str(n.lineno)+' '+cond[:240].replace(chr(10),' '))
   print('BODY='+str((ast.get_source_segment(s,n.body[0]) or '')[:600]).replace(chr(10),' '))
for n in ast.walk(f):
 if isinstance(n,ast.Call):
  fn=ast.get_source_segment(s,n.func) or ''
  if any(x in fn for x in ('subprocess','Popen','os.system','requests.','post_json')):
   print('SIDE_EFFECT_CALL_LINE='+str(n.lineno)+' '+fn[:140])
print('SOURCE_REVIEW_COMPLETED=YES')
PY
echo '===== READ-ONLY E2E RUN EVIDENCE ====='
docker exec -i aiops2-e2e-v1-aiops2-core-1 python - <<'PY'
import json,os,urllib.request
rid='RUN-171493F5FE80D45E'
token=os.getenv('AIOPS_INTERNAL_TOKEN') or os.getenv('ADMIN_TOKEN')
assert token
req=urllib.request.Request('http://127.0.0.1:810/api/runs/'+rid,headers={'Authorization':'Bearer '+token})
with urllib.request.urlopen(req,timeout=15) as r:d=json.load(r)
run=d['run'];assert run['mode']=='DEMO' and run['status']=='RESOLVED'
gates=[g for g in d.get('gates',[]) if g.get('stage')=='POLICY']
assert gates and all(g['state']=='PASS' and g['decision']=='SIMULATE' for g in gates)
print('POLICY_SIMULATE=PASS')
for stage in ('HITL','REMEDIATE','VERIFY'):
 events=[e for e in d.get('events',[]) if e.get('stage')==stage]
 assert events
 print('STAGE='+stage+' EVENTS='+','.join(e.get('event_type','') for e in events))
 for e in events:
  if e.get('event_type')=='STAGE_COMPLETED':
   p=e.get('payload') or {}
   print('STAGE_COMPLETED_SYNTHETIC='+stage+':'+str(p.get('synthetic')))
   assert p.get('synthetic') is True
print('DEMO_STAGE_SYNTHETIC_MARKERS=PASS')
print('NOTE=synthetic event markers alone do not prove absence of external side effects')
PY
echo '===== SAFETY ====='
echo 'HTTP_WRITES=0'
echo 'NEW_WORKFLOWS_STARTED=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.996 ====='
