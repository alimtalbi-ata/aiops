#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CAMPAIGN="FS1130-$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${FS1130_REPORT_DIR:-$HOME/aiops2-qualification-reports}"
mkdir -p "$OUT"
REPORT="$OUT/$CAMPAIGN.jsonl"
echo "FS1130_CAMPAIGN=$CAMPAIGN"
echo "FS1130_REPORT=$REPORT"
echo "FS1130_MODE=DEMO_SYNTHETIC_50_REAL_CORE_TEMPORAL_PIPELINE"
echo "FS1130_PORTAL_7777_MUTATION=NONE"
echo "FS1130_LIVE_EFFECTS=PROHIBITED"
echo "FS1130_WARNING=50 synthetic incidents and runs WILL BE WRITTEN to the shared AIOps2 Core database"
docker exec -i -e "FS1130_CAMPAIGN=$CAMPAIGN" aiops2-rebuild-core python - <<'PY' | tee "$REPORT"
import os,sys,time,json,collections,datetime,requests
from shared.db import db
base="http://127.0.0.1:810"
token=os.getenv("AIOPS_INTERNAL_TOKEN") or os.getenv("ADMIN_TOKEN")
if not token:
 print(json.dumps({"type":"fatal","reason":"internal_token_missing"}),flush=True);sys.exit(2)
headers={"Authorization":"Bearer "+token}
campaign=os.environ["FS1130_CAMPAIGN"]
titles=[
 "SAN fabric errors","RHEL multipath degraded","Storage latency spike","Database query timeout","API 5xx burst",
 "Payment p95 latency","DNS resolution errors","TLS certificate warning","CPU saturation","Memory pressure",
 "Disk capacity threshold","Kafka consumer lag","Network packet loss","Switch interface flaps","Host unavailable",
 "Container restart loop","Temporal queue backlog","Application thread exhaustion","Database connection pool","Replication lag",
 "Backup job failure","NTP clock drift","Service dependency timeout","HTTP gateway errors","Filesystem read-only",
 "Authentication error burst","Redis eviction surge","Message broker disconnect","Storage path failover","Load balancer health",
 "High inode utilization","Kernel I/O errors","API rate limit exceeded","Prometheus scrape failure","Alertmanager delivery delay",
 "Log ingestion gap","Tracing sampling gap","GLPI sync delay","CMDB orphan relation","Unknown asset ownership",
 "Dependency cycle alert","Cross-zone network jitter","Database deadlock","Scheduler missed execution","Certificate expiry",
 "Secret rotation failure","Object storage throttling","Service error budget burn","Deployment regression","Data freshness gap"
]
severities=["P1","P2","P3","P4","UNKNOWN"]
def emit(obj):
 print(json.dumps(obj,ensure_ascii=False,default=str,separators=(",",":")),flush=True)
def post(path,data):
 r=requests.post(base+path,json=data,headers=headers,timeout=25)
 if not r.ok:raise RuntimeError(f"POST {path} HTTP {r.status_code}: {r.text[:180]}")
 return r.json()
def get(path):
 r=requests.get(base+path,timeout=12)
 if not r.ok:raise RuntimeError(f"GET {path} HTTP {r.status_code}")
 return r.json()
def evidence(rid):
 with db() as c:
  a=c.execute("select count(*) from aiops.analysis_records where run_id=%s",(rid,)).fetchone()[0]
  q=c.execute("select count(*) from aiops.critique_records where run_id=%s",(rid,)).fetchone()[0]
  p=c.execute("select count(*) from aiops.policy_decisions where run_id=%s",(rid,)).fetchone()[0]
  e=c.execute("select count(*) from aiops.evidence where provenance->>'run_id'=%s",(rid,)).fetchone()[0]
  effects=c.execute("select count(*) from aiops.effect_receipts e join aiops.action_proposals p on p.proposal_id=e.proposal_id where p.run_id=%s",(rid,)).fetchone()[0]
  events=c.execute("select event_type from aiops.run_events where run_id=%s order by sequence",(rid,)).fetchall()
  return dict(analysis=a,critique=q,policy=p,evidence=e,effects=effects,event_types=[v[0] for v in events])
emit({"type":"start","campaign":campaign,"target":50,"concurrency":2,"timeout_per_run_seconds":300,"mode":"DEMO","note":"50 distinct incident labels; current Worker may reuse a common synthetic SAN evidence scenario; this is not 50 independently simulated root causes"})
active={}
results=[]
created=0
next_index=0
deadline_seconds=300
while next_index<50 or active:
 while next_index<50 and len(active)<2:
  i=next_index;next_index+=1
  sid=f"{campaign}-SC-{i+1:02d}"
  ext=f"{campaign}-{i+1:02d}"
  try:
   post("/api/scenarios/register",{"scenario_id":sid,"name":titles[i],"seed":i+1,"description":f"FS1130 synthetic qualification case {i+1}: {titles[i]}"})
   inc=post("/api/incidents",{"external_id":ext,"title":titles[i],"severity":severities[i%5],"source":"fs1130-load-qualification","synthetic":True,"payload":{"campaign":campaign,"case":i+1,"category":titles[i]}})
   run=post("/api/runs",{"mode":"DEMO","scenario_id":sid,"incident_id":inc["incident_id"],"idempotency_key":ext+"-DEMO"})
   rid=run["run_id"]
   active[rid]={"case":i+1,"title":titles[i],"incident_id":inc["incident_id"],"started":time.monotonic(),"status":"CREATED"}
   created+=1
   post(f"/api/runs/{rid}/execute",{})
   emit({"type":"submitted","case":i+1,"incident_id":inc["incident_id"],"run_id":rid,"mode":"DEMO"})
  except Exception as exc:
   result={"type":"result","case":i+1,"status":"SUBMISSION_FAILED","error":str(exc)[:220]}
   results.append(result);emit(result)
   if len([r for r in results if r["status"]=="SUBMISSION_FAILED"])>=5:
    emit({"type":"abort","reason":"five_submission_failures"});next_index=50;break
 if not active:continue
 time.sleep(5)
 for rid,info in list(active.items()):
  try:
   detail=get(f"/api/runs/{rid}")
   status=detail["run"]["status"]
   info["status"]=status
   if status not in ("RESOLVED","BLOCKED","FAILED","CANCELLED") and time.monotonic()-info["started"]<deadline_seconds:continue
   if status not in ("RESOLVED","BLOCKED","FAILED","CANCELLED"):status="TIMEOUT"
   counts=evidence(rid)
   result={"type":"result","case":info["case"],"title":info["title"],"incident_id":info["incident_id"],"run_id":rid,"status":status,"elapsed_seconds":round(time.monotonic()-info["started"],1),**counts}
   results.append(result);emit(result)
   if counts["effects"]>0:
    emit({"type":"safety_alert","reason":"unexpected_effect_receipt","run_id":rid})
    next_index=50
   del active[rid]
  except Exception as exc:
   if time.monotonic()-info["started"]>=deadline_seconds:
    result={"type":"result","case":info["case"],"run_id":rid,"status":"QUERY_TIMEOUT","error":str(exc)[:180]}
    results.append(result);emit(result);del active[rid]
summary={"type":"summary","campaign":campaign,"submitted":created,"completed":len(results),"status_counts":dict(collections.Counter(r["status"] for r in results)),"with_analysis":sum(r.get("analysis",0)>0 for r in results),"with_critique":sum(r.get("critique",0)>0 for r in results),"with_policy":sum(r.get("policy",0)>0 for r in results),"with_evidence":sum(r.get("evidence",0)>0 for r in results),"total_effect_receipts":sum(r.get("effects",0) for r in results),"median_elapsed_seconds":sorted([r["elapsed_seconds"] for r in results if "elapsed_seconds" in r])[len([r for r in results if "elapsed_seconds" in r])//2] if any("elapsed_seconds" in r for r in results) else None}
emit(summary)
if summary["total_effect_receipts"]>0 or created!=50 or len(results)!=50:sys.exit(1)
PY
echo "FS1130_REPORT=$REPORT"
