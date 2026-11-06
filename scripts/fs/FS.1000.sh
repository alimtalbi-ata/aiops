#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.1000 | PORTAL OBSERVABILITY CMDB INVENTORY ====='
echo '===== CONTAINERS (NAME / IMAGE / STATE / PORTS) ====='
docker ps -a --format '{{.Names}} | {{.Image}} | {{.Status}} | {{.Ports}}' | grep -Ei 'aiops|prometheus|grafana|loki|tempo|postgres|redis|portal' || true
echo '===== E2E NETWORK SERVICES ====='
docker network inspect aiops2-e2e-v1_control --format '{{range .Containers}}{{.Name}} {{.IPv4Address}}{{println}}{{end}}'
echo '===== LOCAL SOURCE TREE (CAPPED) ====='
for dir in /home/aiops/aiops2-v2-delivery /home/aiops/aiops2-fs-demo-source; do
 if [[ -d "$dir" ]]; then
  echo "SOURCE_ROOT=$dir"
  find "$dir" -maxdepth 5 -type f \( -iname '*portal*' -o -iname '*cmdb*' -o -iname '*prometheus*' -o -iname '*grafana*' -o -iname '*dashboard*' -o -iname '*metrics*' -o -iname '*schema*' -o -name 'docker-compose*.yml' -o -name 'compose*.yaml' \) -not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/.venv/*' | sort | head -100
 fi
done
echo '===== E2E API CAPABILITIES (READ ONLY) ====='
docker exec -i aiops2-e2e-v1-aiops2-core-1 python - <<'PY'
import json,urllib.request,urllib.error
for host in ('http://127.0.0.1:810','http://aiops2-policy:813','http://aiops2-evidence:812','http://aiops2-twin:811','http://aiops2-intelligence:817'):
 for path in ('/openapi.json','/metrics'):
  try:
   with urllib.request.urlopen(host+path,timeout=3) as r:
    typ=r.headers.get('content-type','')
    if path=='/openapi.json':
     spec=json.load(r)
     paths=sorted(spec.get('paths',{}))
     filtered=[p for p in paths if any(x in p.lower() for x in ('cmdb','topology','metric','incident','run','evidence','log','scenario','alert','health','gate','demo'))]
     print('API='+host+' PATHS='+json.dumps(filtered[:65]))
    else:
     body=r.read(4096).decode('utf-8','replace')
     print('METRICS='+host+' STATUS='+str(r.status)+' SAMPLE_LINES='+str(len(body.splitlines()))+' CONTENT_TYPE='+typ)
  except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as e:
   print('ENDPOINT='+host+path+' RESULT='+type(e).__name__+' '+str(e)[:120])
PY
echo '===== DATABASE CONTAINER INVENTORY (NO CREDENTIALS) ====='
docker ps --format '{{.Names}} | {{.Image}}' | grep -Ei 'postgres|timescale|mysql|mariadb|clickhouse|redis|mongo|victoria|prometheus' || true
echo 'READ_ONLY=YES'
echo 'WORKFLOWS_STARTED=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.1000 ====='
