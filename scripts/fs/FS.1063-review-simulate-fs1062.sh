#!/usr/bin/env bash
set -euo pipefail
echo "FS1063_MODE=STATIC_AND_SIMULATED_ONLY"
python3 - "$(dirname "$0")/fs1062_native_deploy.py" <<'PY'
import ast,pathlib,sys,types,urllib.error
path=pathlib.Path(sys.argv[1])
source=path.read_text()
tree=ast.parse(source)
compile(source,str(path),"exec")
print("FS1063_SYNTAX=PASS")
assert 'FS1062_EXPLICIT_APPROVAL' in source
assert 'FS1062_NOT_AUTHORIZED' in source
print("FS1063_APPROVAL_GUARD=PASS")
funcs={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
assert {"wait_for_readiness","check_http","rollback"}.issubset(funcs)
assert 'range(1,61)' in ast.get_source_segment(source,funcs["wait_for_readiness"])
assert 'NetworkSettings' in ast.get_source_segment(source,funcs["wait_for_readiness"])
assert 'Ports' in ast.get_source_segment(source,funcs["wait_for_readiness"])
assert 'http://127.0.0.1:7777/health' in ast.get_source_segment(source,funcs["wait_for_readiness"])
print("FS1063_READINESS_GATE_STATIC=PASS")
# Validate that network connections precede readiness and HTTP probes.
positions=[source.index('docker("network","connect",network,NAME)'),source.index('        wait_for_readiness()'),source.index('        for path in ("/health",')]
assert positions==sorted(positions)
print("FS1063_OPERATION_ORDER=PASS")
# Execute extracted functions only; never execute module top-level deployment.
module=ast.Module(body=[funcs["wait_for_readiness"],funcs["rollback"]],type_ignores=[])
ns={"NAME":"aiops2-rebuild-portal","renamed":True,"old_was_running":True,
    "OLD":"old-container","time":types.SimpleNamespace(sleep=lambda n:None)}
class Resp:
 status=200
 def __enter__(self):return self
 def __exit__(self,*a):pass
class Url:
 def __init__(self,fail=False):self.fail=fail
 def urlopen(self,*a,**kw):
  if self.fail:raise urllib.error.URLError("simulated")
  return Resp()
ns["urllib"]=types.SimpleNamespace(request=Url(),error=urllib.error)
ns["inspect"]=lambda name:{"State":{"Running":True},"NetworkSettings":{"Networks":{"aiops2-rebuild-control":{},"aiops2-rebuild-integration":{},"aiops2-rebuild-public":{}},"Ports":{"777/tcp":[{"HostPort":"7777"}]}}}
ns["docker"]=lambda *args,**kw:None
exec(compile(module,str(path),"exec"),ns)
ns["wait_for_readiness"]()
print("FS1063_READINESS_SUCCESS_SIMULATION=PASS")
ns["urllib"].request=Url(fail=True)
try:ns["wait_for_readiness"]()
except RuntimeError as e:
 assert "FS1062_READINESS_TIMEOUT" in str(e)
else:raise AssertionError("readiness timeout was not enforced")
print("FS1063_READINESS_TIMEOUT_SIMULATION=PASS")
calls=[]
ns["docker"]=lambda *args,**kw:calls.append(args)
ns["rollback"]()
assert calls[:4]==[("rm","-f","aiops2-rebuild-portal"),("rename","old-container","aiops2-rebuild-portal"),("update","--restart=unless-stopped","aiops2-rebuild-portal"),("start","aiops2-rebuild-portal")]
print("FS1063_ROLLBACK_SEQUENCE_SIMULATION=PASS")
print("FS1063_RESULT=PASS")
PY
