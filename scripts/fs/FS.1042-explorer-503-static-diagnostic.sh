#!/usr/bin/env bash
# FS.1042 — diagnose isolated explorer HTTP 503 without production secrets.
set -euo pipefail
IMAGE="aiops2-portal:fs1040-sql-guard-candidate"
echo "FS1042_MODE=OFFLINE_STATIC_DIAGNOSTIC"
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
 --env PYTHONDONTWRITEBYTECODE=1 --env AIOPS_INTERNAL_TOKEN=fs1042-dummy \
 --entrypoint python "$IMAGE" -c '
import ast, inspect
import portal.explorer_api as e
source=inspect.getsource(e)
tree=ast.parse(source)
for n in ast.walk(tree):
 if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)): continue
 if n.name in ("_guard","_allowed","_check","_require","catalog","explorer_page","explorer","_authorized","_access"):
  print("FUNCTION="+n.name)
  for sub in ast.walk(n):
   if isinstance(sub,ast.Call) and isinstance(sub.func,ast.Name) and sub.func.id=="HTTPException":
    code=ast.unparse(sub.args[0]) if sub.args else "unknown"
    detail=ast.unparse(sub.args[1]) if len(sub.args)>1 else "unknown"
    print("HTTP_EXCEPTION_STATUS=%s DETAIL_EXPR=%s"%(code,detail[:120]))
   if isinstance(sub,ast.Constant) and isinstance(sub.value,str) and ("CIDR" in sub.value or "EXPLORER_" in sub.value):
    print("ENV_NAME_LITERAL=%r"%sub.value[:100])
for n in ast.walk(tree):
 if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="HTTPException":
  if n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value==503:
   parent=next((fn.name for fn in tree.body if isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)) and fn.lineno<=n.lineno<=fn.end_lineno),"UNKNOWN")
   print("HTTP_503_FUNCTION="+parent)
   if len(n.args)>1: print("HTTP_503_DETAIL_EXPR="+ast.unparse(n.args[1])[:160])
print("FS1042_DIAGNOSTIC=COMPLETE")
'
