#!/usr/bin/env bash
set -euo pipefail
echo "FS1076_MODE=ISOLATED_AUTH_AND_CSP_SOURCE_INSPECTION"
docker run --rm --network none -e AIOPS_INTERNAL_TOKEN=fs1076-isolated-placeholder-token --entrypoint python aiops2-portal:fs1073-csp-candidate -c '
import ast,pathlib
for name in ("/app/portal/main.py","/app/portal/explorer_api.py","/app/portal/fs1051_visual.py"):
 p=pathlib.Path(name)
 if not p.is_file():continue
 source=p.read_text()
 tree=ast.parse(source)
 print("FS1076_FILE="+p.name)
 for n in tree.body:
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and (n.name in ("_check","visual") or "middleware" in n.name.lower()):
   segment=source.splitlines()[n.lineno-1:n.end_lineno]
   print("FS1076_FUNCTION="+n.name+" LINES="+str(n.lineno)+"-"+str(n.end_lineno))
   for line in segment[:65]:
    if any(w in line.lower() for w in ("token","password","secret","authorization","cookie","api_key","bearer")):
     print("FS1076_CODE=[AUTH-RELATED LINE REDACTED]")
    else:print("FS1076_CODE="+line[:180])
  if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=="add_middleware":
   print("FS1076_ADD_MIDDLEWARE_LINE="+str(n.lineno))
print("FS1076_RESULT=COMPLETE")
'
echo "FS1076_PRODUCTION_DEPLOY=NOT_PERFORMED"
