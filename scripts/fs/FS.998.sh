#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.998 | REMEDIATION POLICY GATE CONTRACT TEST ====='
IMAGE=aiops2-worker:fs997-demo-gate-hardened-20261106
EXPECTED=dfa580bb4caeea2e4815f8c3ab560e3b0d54b44fb5dc3abc38b4a3f56cbc8327
ACTUAL="$(docker run --rm --network none --entrypoint python "$IMAGE" -c 'import hashlib;print(hashlib.sha256(open("/app/worker/main.py","rb").read()).hexdigest())')"
[[ "$ACTUAL" == "$EXPECTED" ]] || { echo "IMAGE_INTEGRITY=FAIL SHA=$ACTUAL"; exit 1; }
echo 'IMAGE_INTEGRITY=PASS'
# Pass the test program as a Python -c argument so Docker does not need stdin.
TEST="$(cat <<'PY'
import ast,pathlib
s=pathlib.Path('/app/worker/main.py').read_text()
t=ast.parse(s)
fn=next(n for n in ast.walk(t) if isinstance(n,ast.FunctionDef) and n.name=='_execute_stage_blocking')
guards=[]
for n in ast.walk(fn):
 if not isinstance(n,ast.If):continue
 test=n.test
 if not isinstance(test,ast.Compare) or not isinstance(test.left,ast.Name) or test.left.id!='stage':continue
 if len(test.ops)!=1 or not isinstance(test.ops[0],ast.In):continue
 if len(test.comparators)!=1 or not isinstance(test.comparators[0],(ast.Tuple,ast.List)):continue
 values=test.comparators[0].elts
 if len(values)==2 and all(isinstance(v,ast.Constant) for v in values) and {v.value for v in values}=={'REMEDIATE','VERIFY'}:
  guards.append(n)
assert len(guards)==1,'exactly one remediation guard required; found '+str(len(guards))
node=guards[0]
code=compile(ast.Module(body=[node],type_ignores=[]),'/app/worker/main.py','exec')
def check(stage,mode,run_mode,run_scenario,gates):
 seen=[]
 def get_json(url,token=None):
  seen.append(url)
  return {'run':{'mode':run_mode,'scenario_id':run_scenario},'gates':gates}
 env={'stage':stage,'mode':mode,'scenario':'SCN-GOLDEN-PAYMENT-P1',
      'rid':'RUN-FS998-TEST','CORE':'http://mock-core:810',
      'ADMIN':'offline-test','get_json':get_json}
 try:
  exec(code,env)
 except RuntimeError as exc:
  assert str(exc)=='demo_remediation_requires_policy_simulate',str(exc)
  return False,len(seen)
 return True,len(seen)
pass_gate=[{'stage':'POLICY','state':'PASS','decision':'SIMULATE'}]
cases=[
 ('missing_gate','DEMO','DEMO','SCN-GOLDEN-PAYMENT-P1',[],False),
 ('policy_block','DEMO','DEMO','SCN-GOLDEN-PAYMENT-P1',[{'stage':'POLICY','state':'BLOCKED','decision':'HUMAN_APPROVAL'}],False),
 ('execute_not_simulate','DEMO','DEMO','SCN-GOLDEN-PAYMENT-P1',[{'stage':'POLICY','state':'PASS','decision':'EXECUTE'}],False),
 ('wrong_scenario','DEMO','DEMO','OTHER',pass_gate,False),
 ('wrong_run_mode','DEMO','LIVE','SCN-GOLDEN-PAYMENT-P1',pass_gate,False),
 ('wrong_activity_mode','LIVE','DEMO','SCN-GOLDEN-PAYMENT-P1',pass_gate,False),
 ('authorized_demo','DEMO','DEMO','SCN-GOLDEN-PAYMENT-P1',pass_gate,True),
]
for stage in ('REMEDIATE','VERIFY'):
 for name,mode,run_mode,scenario,gates,expected in cases:
  result,calls=check(stage,mode,run_mode,scenario,gates)
  assert result is expected and calls==1,(stage,name,result,calls)
  print('CASE='+stage+':'+name+' RESULT='+('ALLOW' if result else 'DENY')+' PASS')
print('GATE_CONTRACT_CASES='+str(len(cases)*2))
print('GATE_CONTRACT_RESULT=PASS')
PY
)"
docker run --rm --network none --env AIOPS_INTERNAL_TOKEN=fs998-offline-test --entrypoint python "$IMAGE" -c "$TEST"
echo 'HTTP_WRITES=0'
echo 'NEW_WORKFLOWS_STARTED=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.998 ====='
