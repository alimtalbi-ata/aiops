#!/usr/bin/env bash
# FS.1033: read-only static inspection of the running explorer module.
set -euo pipefail
echo "FS1033_MODE=READ_ONLY_STATIC"
docker exec aiops2-rebuild-portal python -c '
import ast, inspect, json
import portal.explorer_api as module
source=inspect.getsource(module)
tree=ast.parse(source)
print("MODULE=portal.explorer_api")
print("===== CONFIG KEYS REFERENCED IN SOURCE (NAMES ONLY) =====")
names=set()
for node in ast.walk(tree):
    if not isinstance(node,ast.Call): continue
    f=node.func
    if isinstance(f,ast.Attribute) and f.attr in ("getenv","get") and node.args:
        a=node.args[0]
        if isinstance(a,ast.Constant) and isinstance(a.value,str):
            k=a.value
            if any(x in k.upper() for x in ("URL","DSN","DATABASE","DB_","CMDB","GLPI","EXPLORER","PROMETHEUS","TEMPORAL","SQL","READ","CIDR","LIMIT","ROW")):
                names.add(k)
for name in sorted(names): print("CONFIG_KEY="+name)
print("===== ROUTE SIGNATURES =====")
for route in getattr(module,"router",getattr(module,"app",None)).routes if getattr(module,"router",getattr(module,"app",None)) else []:
    fn=getattr(route,"endpoint",None)
    if fn and getattr(route,"path","").startswith("/api/explorer/"):
        print("ROUTE=%s FUNCTION=%s" % (route.path,fn.__name__))
print("===== FUNCTION NAMES / STATIC GUARD HINTS =====")
for node in tree.body:
    if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
        name=node.name
        if any(x in name.lower() for x in ("query","database","preview","table","cmdb","inventory","allow","guard","sql","connect","observe","catalog","auth","cidr")):
            print("FUNCTION="+name)
print("FS1033_STATIC_DISCOVERY=COMPLETE")
'
