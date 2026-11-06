#!/usr/bin/env bash
# FS.1030 — Read-only connectivity and image parity discovery.
set -euo pipefail
echo "FS1030_MODE=READ_ONLY"
for name in aiops2-rebuild-portal aiops2-rebuild-prometheus aiops2-rebuild-twin aiops2-rebuild-core aiops2-rebuild-grafana aiops2-rebuild-glpi; do
  if docker inspect "$name" >/dev/null 2>&1; then
    docker inspect "$name" --format 'SERVICE={{.Name}} IMAGE={{.Config.Image}} NETWORKS={{range $n,$_ := .NetworkSettings.Networks}}{{$n}},{{end}}'
  else
    echo "SERVICE=$name STATUS=NOT_FOUND"
  fi
done
echo "===== PORTAL IMAGE ROUTES (NO EXEC) ====="
docker exec aiops2-rebuild-portal python -c 'from portal.main import app; print("\\n".join("ROUTE="+r.path for r in app.routes if hasattr(r,"path")))' 2>/dev/null || echo 'PORTAL_ROUTE_INSPECTION=UNKNOWN'
echo "===== PORTAL NETWORK API CHECK ====="
docker exec aiops2-rebuild-portal python -c '
import urllib.request
for name,url in [
 ("prometheus_ready","http://aiops2-rebuild-prometheus:9090/-/ready"),
 ("prometheus_targets","http://aiops2-rebuild-prometheus:9090/api/v1/targets?state=active"),
 ("twin_health","http://aiops2-rebuild-twin:811/health"),
 ("twin_graph","http://aiops2-rebuild-twin:811/api/twin/graph"),
 ("core_health","http://aiops2-rebuild-core:810/health"),
]:
 try:
  with urllib.request.urlopen(url,timeout=4) as r:
   print("PROBE=%s HTTP=%s CONTENT_TYPE=%s"%(name,r.status,r.headers.get("content-type","UNKNOWN")))
 except Exception as e:
  print("PROBE=%s STATUS=UNKNOWN ERROR_TYPE=%s"%(name,type(e).__name__))
'
echo "FS1030_DISCOVERY=COMPLETE"
