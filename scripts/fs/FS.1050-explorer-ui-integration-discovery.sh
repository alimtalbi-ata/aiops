#!/usr/bin/env bash
set -euo pipefail
echo "FS1050_MODE=READ_ONLY_UI_INTEGRATION_DISCOVERY"
docker exec -i aiops2-rebuild-portal python - <<'PY'
import ast,inspect
from pathlib import Path
import portal.explorer_api as e
print("FS1050_EXPLORER_SOURCE="+str(inspect.getfile(e)))
for name in ("router","_check","_deny_untrusted","explorer_page","catalog","observe"):
 o=getattr(e,name,None)
 if o is not None:
  try:sig=str(inspect.signature(o))
  except Exception:sig="unknown"
  print("FS1050_SYMBOL="+name+" SIGNATURE="+sig)
p=Path(inspect.getfile(e)); tree=ast.parse(p.read_text())
for n in ast.walk(tree):
 if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
  if n.name in ("_check","_deny_untrusted","explorer_page","catalog","observe","_upstream"):
   print("FS1050_FUNCTION="+n.name+" LINE="+str(n.lineno)+" ARGS="+",".join(a.arg for a in n.args.args))
   for deco in n.decorator_list:
    if isinstance(deco,ast.Call) and isinstance(deco.func,ast.Attribute):
     print("FS1050_DECORATOR="+n.name+" METHOD="+deco.func.attr+" PATH="+repr(deco.args[0].value) if deco.args and isinstance(deco.args[0],ast.Constant) else "FS1050_DECORATOR="+n.name+" UNKNOWN")
for path in ("/app/portal/templates","/app/portal/static","/app/portal"):
 p=Path(path)
 if p.is_dir():
  matches=sorted(x.name for x in p.iterdir() if x.is_file() and any(k in x.name.lower() for k in ("explorer","theme","main","ui")))
  print("FS1050_ASSETS="+path+" FILES="+",".join(matches[:40]))
PY
echo "FS1050_DISCOVERY=COMPLETE"
