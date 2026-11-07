#!/usr/bin/env bash
set -euo pipefail
CB=aiops2-rebuild-cloudbeaver
echo "FS1118_MODE=READ_ONLY_CLOUDBEAVER_DRIVER_DIAGNOSTICS"
echo "FS1118_CONTAINER=$(docker inspect "$CB" --format '{{.State.Status}} {{.Config.Image}}')"
echo "FS1118_HTTP=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8978/ || true)"
echo "FS1118_DATASOURCE_CONFIG_BEGIN"
docker exec "$CB" sh -c 'cat /opt/cloudbeaver/workspace/GlobalConfiguration/.dbeaver/data-sources.json' | python3 -c '
import json,sys
cfg=json.load(sys.stdin)
for key,val in sorted(cfg.get("connections",{}).items()):
    c=val.get("configuration") or {}
    print("ID=%s PROVIDER=%s DRIVER=%s HOST=%s PORT=%s DATABASE=%s" % (key,val.get("provider"),val.get("driver"),c.get("host"),c.get("port"),c.get("database")))
'
echo "FS1118_DATASOURCE_CONFIG_END"
echo "FS1118_DRIVER_METADATA_BEGIN"
docker exec "$CB" sh -c '
find /opt/cloudbeaver -type f \( -name "*drivers*.xml" -o -name "*drivers*.json" -o -name "plugin.xml" \) 2>/dev/null |
  head -80 |
  while IFS= read -r f; do
    if grep -Eiq "mariadb|postgresql|mysql" "$f" 2>/dev/null; then
      echo "FILE=$f"
      grep -Ein -m 6 "mariadb|postgresql|mysql" "$f" 2>/dev/null | cut -c1-240 || true
    fi
  done
' | head -100
echo "FS1118_DRIVER_METADATA_END"
echo "FS1118_LOGS_BEGIN"
docker logs --since 8m "$CB" 2>&1 | grep -E 'DataSourceSerializerModern|DBWebExceptionAccessDenied|GraphQL call failed' | tail -24 || true
echo "FS1118_LOGS_END"
echo "FS1118_RESULT=DIAGNOSTICS_ONLY"
echo "FS1118_RESTART=NONE"
echo "FS1118_MUTATIONS=NONE"
