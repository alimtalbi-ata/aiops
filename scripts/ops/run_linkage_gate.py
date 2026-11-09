#!/usr/bin/env python3
"""Read-only AIOps2 per-run trace gate. No POST, deploy, ticket creation or approval.

Runs on Debian with Docker access. Uses live Core GET and PostgreSQL READ ONLY.
An externally observed GLPI ticket is a *lead*, never treated as verified.
"""
import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

RUN_RE = re.compile(r"^RUN-[A-Z0-9-]{6,80}$")
CORE = "aiops2-rebuild-core"
PG = "aiops2-rebuild-postgres"

def execute(cmd, stdin=None):
    p = subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=35)
    if p.returncode:
        raise RuntimeError(f"command failed: {cmd[0]} exit={p.returncode}")
    return p.stdout

def pg_query(sql):
    script = 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -X -A -t -v ON_ERROR_STOP=1'
    out = execute(["docker","exec","-i",PG,"sh","-c",script],
                  "BEGIN TRANSACTION READ ONLY;\n"+sql+"\nCOMMIT;\n")
    records = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    if len(records) != 1:
        raise RuntimeError("unexpected database response")
    return records[0]

def core_get(run_id):
    script = """import json,os,sys,urllib.request,urllib.error
rid=sys.argv[1]
token=os.getenv('AIOPS_INTERNAL_TOKEN') or os.getenv('ADMIN_TOKEN')
headers={'Accept':'application/json'}
if token: headers['Authorization']='Bearer '+token
out={}
for key,path in [('run','/api/runs/'+rid),('evidence','/api/runs/'+rid+'/evidence'),
                 ('policy_status','/api/noc/runs/'+rid+'/policy-status'),
                 ('ai_ledger','/api/runs/'+rid+'/ai-ledger')]:
 try:
  request=urllib.request.Request('http://127.0.0.1:810'+path,headers=headers,method='GET')
  with urllib.request.urlopen(request,timeout=7) as r:
   obj=json.load(r)
   if key=='run':
    if isinstance(obj,dict):
     candidates=[obj]
     for k in ('run','data','result'):
      if isinstance(obj.get(k),dict):
       candidates.append(obj[k])
       if isinstance(obj[k].get('run'),dict): candidates.append(obj[k]['run'])
     match=next((x for x in candidates if x.get('incident_id') and x.get('run_id')),None)
     if match:
      events=match.get('events',obj.get('events',[]))
      out[key]={'http':r.status,'parse_status':'PARSED','run_id':match.get('run_id'),
                'incident_id':match.get('incident_id'),'status':match.get('status'),
                'event_count':len(events) if isinstance(events,list) else 0}
     else: out[key]={'http':r.status,'parse_status':'UNRECOGNIZED','keys':list(obj)[:15]}
    else: out[key]={'http':r.status,'parse_status':'UNRECOGNIZED'}
   elif key=='evidence':
    out[key]={'http':r.status,'count':len(obj.get('items',[])) if isinstance(obj,dict) else None}
   elif key=='ai_ledger':
    if not isinstance(obj,dict) or obj.get('run_id')!=rid:
     raise ValueError('ledger Run identity mismatch')
    fields={
     'analyses':('analysis_id','revision','contract_version','provider','model','prompt_version','evidence_ids','evidence_set_hash','output','confidence','status','created_at'),
     'critiques':('critique_id','analysis_id','contract_version','provider','model','validated','issues','evidence_ids','output','diagnostic_confidence','created_at'),
     'policy_decisions':('policy_decision_id','analysis_id','critique_id','policy_version','decision','state','reasons','created_at')}
    projected={'run_id':rid}
    for collection,allowed in fields.items():
     rows=obj.get(collection)
     if not isinstance(rows,list):raise ValueError('invalid ledger collection')
     projected[collection]=[{k:row[k] for k in allowed if k in row}
                            for row in rows if isinstance(row,dict)]
    out[key]={'http':r.status,'accessible':True,'data':projected}
   elif key=='policy_status':
    allowed=('schema','run_id','incident_id','mode','run_status','policy_gate_state','policy_decision','policy_gate_recorded','explanation_code','provenance')
    if not isinstance(obj,dict) or obj.get('run_id')!=rid:raise ValueError('policy Run identity mismatch')
    out[key]={'http':r.status,'accessible':True,'data':{k:obj[k] for k in allowed if k in obj}}
   else: out[key]={'http':r.status,'accessible':True}
 except urllib.error.HTTPError as e: out[key]={'http':e.code,'accessible':False}
 except Exception as e: out[key]={'error':type(e).__name__}
print(json.dumps(out))
"""
    return json.loads(execute(["docker","exec","-i",CORE,"python3","-c",script,run_id]))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-id",required=True)
    p.add_argument("--observed-glpi-ticket",type=int,
                   help="External observation only; NOT verified by this tool")
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    if not RUN_RE.fullmatch(args.run_id):
        p.error("invalid run ID")
    if args.observed_glpi_ticket is not None and args.observed_glpi_ticket < 1:
        p.error("ticket must be positive")
    rid=args.run_id
    sql="""
SELECT json_build_object(
 'run', (SELECT row_to_json(x) FROM (
    SELECT run_id, incident_id, status FROM aiops.runs WHERE run_id='%(rid)s') x),
 'critic_outbox', (SELECT coalesce(json_agg(row_to_json(x)),'[]'::json) FROM (
    SELECT run_id,status,policy_decision_id,attempts,reconciled_at,last_error
    FROM aiops.critic_denial_outbox WHERE run_id='%(rid)s') x),
 'glpi_links', (SELECT coalesce(json_agg(row_to_json(x)),'[]'::json) FROM (
    SELECT g.incident_id,g.glpi_ticket_id,g.state,g.confirmed_at
    FROM aiops.glpi_ticket_links g JOIN aiops.runs r ON r.incident_id=g.incident_id
    WHERE r.run_id='%(rid)s') x),
 'itsm_xref', (SELECT coalesce(json_agg(row_to_json(x)),'[]'::json) FROM (
    SELECT x.incident_id,x.ticket_id,x.glpi_ticket_readback_verified
    FROM aiops.itsm_xref_events x JOIN aiops.runs r ON r.incident_id=x.incident_id
    WHERE r.run_id='%(rid)s') x)
)::text;
""" % {"rid":rid}
    report={"schema":"aiops2-run-linkage-gate-v1","run_id":rid,
            "collected_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "read_only":True}
    try:
        report["database"]=pg_query(sql)
        report["core"]=core_get(rid)
        db=report["database"]
        checks={}
        checks["core_run"]= "PASS" if db.get("run") else "FAIL"
        core_run=report["core"].get("run",{})
        db_run=db.get("run") or {}
        if core_run.get("http") in (401,403):
            checks["core_api"]="AUTH_REQUIRED"
        elif core_run.get("http")==404:
            checks["core_api"]="FAIL"
        elif core_run.get("parse_status")!="PARSED" or not db_run:
            checks["core_api"]="UNKNOWN"
        elif core_run.get("incident_id")==db_run.get("incident_id") and core_run.get("run_id")==db_run.get("run_id"):
            checks["core_api"]="PASS"
        else:
            checks["core_api"]="FAIL"
        checks["evidence_api"]= "PASS" if report["core"].get("evidence",{}).get("http")==200 else "UNKNOWN"
        checks["critic_policy_outbox"]= "PASS" if any(
            x.get("status")=="RECONCILED" and x.get("policy_decision_id")
            for x in db.get("critic_outbox",[])) else "UNVERIFIED"
        checks["glpi_core_link"]= "PASS" if any(
            x.get("state")=="CONFIRMED" and x.get("glpi_ticket_id") is not None
            for x in db.get("glpi_links",[])) else "MISSING"
        checks["itsm_readback"]= "PASS" if any(
            x.get("glpi_ticket_readback_verified") is True
            for x in db.get("itsm_xref",[])) else "UNVERIFIED"
        checks["temporal_worker_execution"]="UNVERIFIED"
        checks["hitl_action_binding"]="UNVERIFIED"
        if args.observed_glpi_ticket is not None:
            report["external_glpi_observation"]={"ticket_id":args.observed_glpi_ticket,
                 "verification":"USER_OBSERVED_NOT_API_VERIFIED"}
            linked={int(x["glpi_ticket_id"]) for x in db.get("glpi_links",[])
                    if x.get("glpi_ticket_id") is not None}
            checks["observed_glpi_link"]=("PASS" if args.observed_glpi_ticket in linked
                                          else "MISSING")
        report["checks"]=checks
        report["verdict"]="PASS" if all(x=="PASS" for x in checks.values()) else "HOLD"
    except Exception as e:
        report["verdict"]="HOLD"
        report["error"]=type(e).__name__+":"+str(e)[:100]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print("VERDICT:",report["verdict"],"RUN:",rid,"REPORT:",args.output)
    for key,value in report.get("checks",{}).items():
        print(f"  {key}: {value}")
    return 0 if report["verdict"]=="PASS" else 2

if __name__=="__main__":
    sys.exit(main())
