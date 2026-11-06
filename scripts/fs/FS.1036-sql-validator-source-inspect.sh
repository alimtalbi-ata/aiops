#!/usr/bin/env bash
# FS.1036: inspect only the deployed SQL validator and its direct call sites.
# No SQL execution, no network, no secret or full module export.
set -euo pipefail
echo "FS1036_MODE=READ_ONLY_SOURCE_INSPECTION"
docker exec aiops2-rebuild-portal python -c '
import ast,hashlib,inspect
import portal.explorer_api as m
source=inspect.getsource(m)
tree=ast.parse(source)
print("MODULE_SHA256="+hashlib.sha256(source.encode()).hexdigest())
for node in tree.body:
 if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)): continue
 if node.name=="_safe_query":
  print("===== SAFE_QUERY_SOURCE_BEGIN =====")
  print(ast.get_source_segment(source,node))
  print("===== SAFE_QUERY_SOURCE_END =====")
for node in ast.walk(tree):
 if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=="_safe_query":
  parent=next((fn.name for fn in tree.body if isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)) and fn.lineno<=node.lineno<=fn.end_lineno),"UNKNOWN")
  print("SAFE_QUERY_CALLER="+parent)
print("FS1036_SOURCE_DISCOVERY=COMPLETE")
'
