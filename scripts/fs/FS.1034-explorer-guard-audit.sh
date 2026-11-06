#!/usr/bin/env bash
# FS.1034 — inspect AST of production explorer; no credentials, queries or records emitted.
set -euo pipefail
echo "FS1034_MODE=READ_ONLY_STATIC"
docker exec aiops2-rebuild-portal python -c '
import ast, inspect
import portal.explorer_api as m
tree=ast.parse(inspect.getsource(m))
targets={"_connection","_safe_query","_glpi_inventory","catalog","observe","inventory_list","inventory_detail","tables","preview","query"}
for node in tree.body:
 if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) or node.name not in targets: continue
 print("===== FUNCTION=%s ====="%node.name)
 args=[a.arg for a in node.args.posonlyargs+node.args.args+node.args.kwonlyargs]
 print("PARAMETERS="+",".join(args))
 calls=set(); strings=set(); env=set()
 for n in ast.walk(node):
  if isinstance(n,ast.Call):
   f=n.func
   name=(f.id if isinstance(f,ast.Name) else f.attr if isinstance(f,ast.Attribute) else "other")
   if name in {"connect","execute","fetchall","fetchone","urlopen","getenv","get","startswith","match","fullmatch","search","raise_for_status","HTTPException","is_allowed","_safe_query","_connection","_glpi_inventory"}: calls.add(name)
   if isinstance(f,ast.Attribute) and isinstance(f.value,ast.Attribute) and isinstance(f.value.value,ast.Name) and f.value.value.id=="os" and f.value.attr=="environ" and f.attr=="get" and n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str): env.add(n.args[0].value)
   if isinstance(f,ast.Attribute) and isinstance(f.value,ast.Name) and f.value.id=="os" and f.attr=="getenv" and n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str): env.add(n.args[0].value)
  if isinstance(n,ast.Constant) and isinstance(n.value,str):
   value=n.value
   if value.isupper() and 3<=len(value)<=70 and all(c.isupper() or c.isdigit() or c=="_" for c in value): strings.add(value)
 print("CALL_HINTS="+",".join(sorted(calls)))
 print("ENV_KEYS="+",".join(sorted(env)))
 print("UPPERCASE_CONSTANTS="+",".join(sorted(strings))[:1200])
 print("HAS_RAISE="+str(any(isinstance(n,ast.Raise) for n in ast.walk(node))))
 print("HAS_TRY="+str(any(isinstance(n,ast.Try) for n in ast.walk(node))))
print("FS1034_STATIC_AUDIT=COMPLETE")
'
