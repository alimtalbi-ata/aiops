#!/usr/bin/env bash
# FS.1032: audit configuration metadata only, no secret values or DB queries.
set -euo pipefail
echo "FS1032_MODE=READ_ONLY"
docker exec aiops2-rebuild-portal python -c '
import inspect, json, os, urllib.request
from portal.main import app
print("===== EXPLORER ROUTE IMPLEMENTATIONS =====")
for route in app.routes:
    path=getattr(route,"path","")
    if path.startswith("/api/explorer/") or path.startswith("/explorer/"):
        endpoint=getattr(route,"endpoint",None)
        if endpoint:
            code=getattr(endpoint,"__code__",None)
            filename=code.co_filename if code else "UNKNOWN"
            print("ROUTE=%s MODULE=%s FUNCTION=%s SOURCE=%s" % (path,getattr(endpoint,"__module__","UNKNOWN"),getattr(endpoint,"__name__","UNKNOWN"),filename))
print("===== RELEVANT CONFIG VARIABLE NAMES (VALUES REDACTED) =====")
words=("EXPLORER","CMDB","GLPI","PROMETHEUS","DATABASE","POSTGRES","TEMPORAL","LOKI","TEMPO","N8N","CORE")
for key in sorted(os.environ):
    if any(word in key.upper() for word in words):
        print("ENV_NAME=%s VALUE=REDACTED" % key)
print("===== CATALOG CONFIGURATION FLAGS =====")
try:
    with urllib.request.urlopen("http://127.0.0.1:777/api/explorer/catalog",timeout=6) as response:
        catalog=json.load(response)
    for source in catalog.get("databases",[]):
        print("DB_ID=%s ENGINE=%s CONFIGURED=%s" % (source.get("id","UNKNOWN"),source.get("engine","UNKNOWN"),source.get("configured","UNKNOWN")))
    for key,value in sorted(catalog.get("services",{}).items()):
        print("SERVICE=%s CONFIGURED=%s" % (key,value))
    print("MODE=%s MAX_ROWS=%s" % (catalog.get("mode","UNKNOWN"),catalog.get("max_rows","UNKNOWN")))
except Exception as e:
    print("CATALOG_STATUS=UNKNOWN ERROR_TYPE=%s" % type(e).__name__)
print("FS1032_DISCOVERY=COMPLETE")
'
