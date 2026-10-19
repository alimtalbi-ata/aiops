from __future__ import annotations
import json, logging, os, hmac
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from .policy import evaluate

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
log=logging.getLogger("aiops2.api")
DATABASE_URL=os.environ["DATABASE_URL"]
API_KEY=os.environ["AIOPS2_API_KEY"]
app=FastAPI(title="AIOps 2.0 Core API",version="2.0.0",
 description="Incident intake and evidence-aware advisory analysis. Remediation is disabled.")

class IncidentIn(BaseModel):
 model_config=ConfigDict(extra="forbid")
 incident_id:str|None=Field(default=None,min_length=1,max_length=128)
 source:str=Field(min_length=1,max_length=128)
 title:str=Field(min_length=1,max_length=512)
 description:str=Field(default="",max_length=12000)
 severity:str=Field(default="UNKNOWN",max_length=16)
 ci_id:str|None=Field(default=None,max_length=256)
 idempotency_key:str|None=Field(default=None,max_length=256)
 evidence:list[dict[str,Any]]=Field(default_factory=list,max_length=100)
 labels:dict[str,str]=Field(default_factory=dict)

class AnalyzeIn(BaseModel):
 model_config=ConfigDict(extra="forbid")
 incident_id:str=Field(min_length=1,max_length=128)
 evidence:list[dict[str,Any]]=Field(default_factory=list,max_length=100)
 proposed_action:str=Field(default="observe",max_length=128)
 confidence:float=Field(default=0.5,ge=0.0,le=1.0)

def db(): return psycopg.connect(DATABASE_URL,row_factory=dict_row,connect_timeout=5)
def require_key(key:str|None):
 if not key or not hmac.compare_digest(key,API_KEY): raise HTTPException(status_code=401,detail="invalid_api_key")

@app.get("/health")
def health(): return {"status":"ok","service":"aiops2-core","version":"2.0.0"}

@app.get("/ready")
def ready():
 try:
  with db() as conn,conn.cursor() as cur:
   cur.execute("SELECT 1"); cur.fetchone()
  return {"status":"ready","database":"ok"}
 except Exception as exc:
  log.warning("readiness failed: %s",type(exc).__name__)
  raise HTTPException(status_code=503,detail="database_unavailable")

@app.post("/v1/incidents",status_code=201)
def ingest(body:IncidentIn,x_api_key:str|None=Header(default=None)):
 require_key(x_api_key)
 iid=body.incident_id or f"INC-{uuid4().hex[:16].upper()}"
 idem=body.idempotency_key or iid
 try:
  with db() as conn,conn.cursor() as cur:
   cur.execute("""INSERT INTO incidents
    (incident_id,idempotency_key,source,title,description,severity,ci_id,evidence,labels,created_at,updated_at)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,now(),now())
    ON CONFLICT (idempotency_key) DO UPDATE SET updated_at=now()
    RETURNING incident_id,idempotency_key,source,title,description,severity,ci_id,evidence,labels,created_at,updated_at""",
    (iid,idem,body.source,body.title,body.description,body.severity.upper(),body.ci_id,
     json.dumps(body.evidence),json.dumps(body.labels)))
   row=cur.fetchone()
  return {"incident":row,"idempotent_key":idem}
 except Exception:
  log.exception("incident intake failed")
  raise HTTPException(status_code=503,detail="incident_persistence_failed")

@app.get("/v1/incidents")
def list_incidents(limit:int=Query(default=50,ge=1,le=200),x_api_key:str|None=Header(default=None)):
 require_key(x_api_key)
 with db() as conn,conn.cursor() as cur:
  cur.execute("""SELECT incident_id,source,title,description,severity,ci_id,evidence,labels,created_at,updated_at
   FROM incidents ORDER BY created_at DESC LIMIT %s""",(limit,))
  rows=cur.fetchall()
 return {"count":len(rows),"items":rows}

@app.post("/v1/analyze")
def analyze(body:AnalyzeIn,x_api_key:str|None=Header(default=None)):
 require_key(x_api_key)
 with db() as conn,conn.cursor() as cur:
  cur.execute("SELECT incident_id,severity,title,description,ci_id,evidence FROM incidents WHERE incident_id=%s",(body.incident_id,))
  incident=cur.fetchone()
 if not incident: raise HTTPException(status_code=404,detail="incident_not_found")
 evidence=body.evidence or incident.get("evidence") or []
 analysis={"severity":str(incident["severity"]).upper(),"confidence":body.confidence,
  "evidence":evidence,"proposed_action":body.proposed_action,
  "analysis_mode":"deterministic_policy_baseline",
  "limitations":["No LLM inference performed","No CMDB/RAG enrichment performed"]}
 policy=evaluate(incident,analysis)
 result={"incident_id":body.incident_id,"analysis":analysis,"policy":policy,
  "created_at":datetime.now(timezone.utc).isoformat()}
 with db() as conn,conn.cursor() as cur:
  cur.execute("INSERT INTO analyses (incident_id,analysis,policy,created_at) VALUES (%s,%s::jsonb,%s::jsonb,now()) RETURNING id",
   (body.incident_id,json.dumps(analysis),json.dumps(policy)))
  result["analysis_record_id"]=cur.fetchone()["id"]
 return result
