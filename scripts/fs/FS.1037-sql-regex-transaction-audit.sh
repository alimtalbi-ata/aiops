#!/usr/bin/env bash
# FS.1037 — bounded, read-only inspection of SQL guard constants and transaction enforcement.
set -euo pipefail
echo "FS1037_MODE=READ_ONLY_STATIC"
docker exec aiops2-rebuild-portal python -c '
import ast, inspect, re
import portal.explorer_api as m
for key in ("SQL_FORBIDDEN","SQL_START","SQL_DANGEROUS"):
 value=getattr(m,key,None)
 if isinstance(value,re.Pattern):
  print("REGEX_NAME=%s FLAGS=%s PATTERN=%r"%(key,value.flags,value.pattern))
 else: print("REGEX_NAME=%s TYPE=%s"%(key,type(value).__name__))
source=inspect.getsource(m)
tree=ast.parse(source)
for fn in tree.body:
 if not isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)) or fn.name not in ("_run","_connection"): continue
 print("===== FUNCTION=%s ====="%fn.name)
 for n in ast.walk(fn):
  if isinstance(n,ast.Call):
   callee=n.func
   name=callee.id if isinstance(callee,ast.Name) else callee.attr if isinstance(callee,ast.Attribute) else "unknown"
   if name in ("execute","connect","cursor","_safe_query","_connection","rollback","commit"):
    print("CALL=%s"%name)
  if isinstance(n,ast.Constant) and isinstance(n.value,str):
   s=n.value.strip()
   if any(term in s.upper() for term in ("READ ONLY","READ_ONLY","STATEMENT_TIMEOUT","SET TRANSACTION","BEGIN","ROLLBACK","AUTOCOMMIT")):
    print("TRANSACTION_CONTROL_LITERAL=%r"%s[:180])
print("FS1037_GUARD_DISCOVERY=COMPLETE")
'
