#!/usr/bin/env bash
set -euo pipefail
CB=aiops2-rebuild-cloudbeaver
echo "FS1123_MODE=READ_ONLY_CONNECTION_REGISTRY_DIAGNOSTICS"
echo "FS1123_SQL_MUTATION=NONE"
echo "FS1123_PORTAL_MUTATION=NONE"
echo "FS1123_CONTAINER=$(docker inspect "$CB" --format '{{.State.Status}} {{.Config.Image}}')"
echo "FS1123_HTTP=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8978/ || true)"
echo "FS1123_DATASOURCES_BEGIN"
docker exec "$CB" sh -c 'cat /opt/cloudbeaver/workspace/GlobalConfiguration/.dbeaver/data-sources.json' | python3 -c '
import json,sys
cfg=json.load(sys.stdin)
for key,conn in sorted(cfg.get("connections",{}).items()):
 conf=conn.get("configuration") or {}
 print("ID=%s PROVIDER=%s DRIVER=%s HOST=%s DATABASE=%s" % (key,conn.get("provider"),conn.get("driver"),conf.get("host"),conf.get("database")))
print("COUNT="+str(len(cfg.get("connections",{}))))
'
echo "FS1123_DATASOURCES_END"
echo "FS1123_POLICY_BEGIN"
docker exec "$CB" sh -c 'cat /opt/cloudbeaver/workspace/.data/.cloudbeaver.runtime.conf' | python3 -c '
import json,sys
app=json.load(sys.stdin).get("app",{})
for k in ("enabledDrivers","disabledDrivers"):
 print(k+"="+",".join(app.get(k,[])))
'
echo "FS1123_POLICY_END"
echo "FS1123_LOGS_BEGIN"
docker logs --since 15m "$CB" 2>&1 | grep -Ei "aiops2-glpi|connection .*not found|datasource|accessdenied|driver disabled|driver.*missing" | tail -45 | sed -E 's/(password|pwd|token|secret)([=: ]+)[^ ,;]+/\1\2[REDACTED]/Ig' || true
echo "FS1123_LOGS_END"
echo "FS1123_NEXT=COMPARE_FILE_WITH_RUNTIME_AND_RELOAD_UI_SESSION"
echo "FS1123_RESULT=DIAGNOSTICS_ONLY"
