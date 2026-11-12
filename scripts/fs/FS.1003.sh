#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.1003 | PROMETHEUS TWIN 503 ROOT CAUSE ====='
echo 'MODE=READ_ONLY'
echo '===== PROMETHEUS TARGET DETAIL ====='
docker exec aiops2-rebuild-prometheus sh -c 'wget -q -T 5 -O - "http://127.0.0.1:9090/api/v1/targets?state=active"' | python3 -c '
import json,sys
d=json.load(sys.stdin)
for t in d.get("data",{}).get("activeTargets",[]):
 if t.get("labels",{}).get("job") not in ("aiops2-core","aiops2-twin"):continue
 for k in ("scrapeUrl","health","lastError","lastScrape","lastScrapeDuration","scrapeInterval"):
  print("TARGET_"+str(t.get("labels",{}).get("job"))+"_"+k+"="+str(t.get(k,"")))
'
echo '===== TWIN FROM PRODUCTION PROMETHEUS NETWORK ====='
docker exec aiops2-rebuild-prometheus sh -c 'wget -S -T 6 -O - http://aiops2-twin:811/metrics 2>&1' | head -c 1600 || true
echo
echo '===== TWIN LOCAL HTTP PROBE ====='
docker exec aiops2-rebuild-twin python - <<'PY'
import urllib.request,urllib.error
for path in ('/health','/metrics'):
 try:
  with urllib.request.urlopen('http://127.0.0.1:811'+path,timeout=5) as r:
   print('TWIN_LOCAL='+path+' HTTP='+str(r.status)+' TYPE='+str(r.headers.get('Content-Type'))+' SAMPLE='+repr(r.read(280).decode('utf-8','replace')))
 except Exception as e:print('TWIN_LOCAL='+path+' ERROR='+type(e).__name__+' '+str(e)[:180])
PY
echo '===== TWIN HEALTH / RESOURCE / NETWORK ====='
docker inspect aiops2-rebuild-twin --format 'TWIN_RUNNING={{.State.Running}} RESTARTS={{.RestartCount}} OOM={{.State.OOMKilled}} HEALTH={{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}'
docker stats --no-stream --format '{{.Name}} CPU={{.CPUPerc}} MEM={{.MemUsage}}' aiops2-rebuild-twin aiops2-rebuild-postgres
echo '===== RECENT TWIN LOGS (MAX 50 LINES; REVIEW BEFORE SHARING SECRETS) ====='
docker logs --tail 50 --since 15m aiops2-rebuild-twin 2>&1 | sed -E 's/(Bearer )[A-Za-z0-9._~-]+/\1[REDACTED]/g; s/((token|password|secret|api_key)[=: ]+)[^ ,;]+/\1[REDACTED]/Ig' | tail -50
echo '===== PROMETHEUS ALERT DETAILS ====='
docker exec aiops2-rebuild-prometheus sh -c 'wget -q -T 5 -O - http://127.0.0.1:9090/api/v1/alerts' | python3 -c '
import json,sys
d=json.load(sys.stdin)
for a in d.get("data",{}).get("alerts",[]):
 if a.get("labels",{}).get("alertname")=="AIOps2FilesystemUsageHigh":
  print("ALERT_STATE="+str(a.get("state")))
  print("ALERT_LABELS="+json.dumps({k:v for k,v in a.get("labels",{}).items() if k not in ("token","password","secret")},sort_keys=True))
  print("ALERT_ACTIVE_AT="+str(a.get("activeAt")))
'
echo 'HTTP_WRITES=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.1003 ====='
