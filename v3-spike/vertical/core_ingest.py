"""Isolated synthetic Core creation; no execution command."""
import hashlib
import json
from http.client import HTTPConnection
from ingestion_demo import ingest
from core_read import read_run

def create_run(records,port,token):
    result=ingest(records)
    if len(result["incidents"])!=1:
        raise ValueError("One correlated incident required")
    if type(port) is not int or not 1024<=port<=65535 or port in (7770,7777,7790):
        raise ValueError("Invalid lab port")
    if not isinstance(token,str) or not 32<=len(token)<=256 or any(not 33<=ord(c)<=126 for c in token):
        raise ValueError("Invalid token")
    incident=result["incidents"][0]
    digest=hashlib.sha256(json.dumps(incident,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    external="CI-INGEST-"+digest[:32]
    def post(path,body):
        conn=HTTPConnection("127.0.0.1",port,timeout=5)
        try:
            conn.request("POST",path,json.dumps(body),{"Authorization":"Bearer "+token,"Content-Type":"application/json"})
            response=conn.getresponse()
            raw=response.read(65537)
            if response.status!=200 or len(raw)>65536:
                raise ValueError("Core creation unavailable")
            return json.loads(raw)
        finally:
            conn.close()
    created=post("/api/incidents",{"external_id":external,"title":"Synthetic correlated incident","severity":"P1" if incident["severity"]=="critical" else "P3","source":"v3-synthetic-ingestion","synthetic":True,"payload":{"classification":"SYNTHETIC_INGESTION","batch_sha256":digest}})
    if created.get("incident_id")!="INC-"+external or created.get("synthetic") is not True:
        raise ValueError("Unverified incident")
    run=post("/api/runs",{"incident_id":created["incident_id"],"mode":"DEMO","scenario_id":"CI-INGEST","idempotency_key":"v3-ingest-"+digest})
    verified=read_run(port,token,run["run_id"])
    if verified["run"]["incident_id"]!=created["incident_id"] or verified["run"]["mode"]!="DEMO":
        raise ValueError("Unverified run binding")
    return {"core":verified,"correlation":result,"production_authorized":False}

def create_and_persist(records,core_port,token,evidence_port):
    from ingestion_store import persist
    result=create_run(records,core_port,token)
    run=result["core"]["run"]
    stored=persist(records,evidence_port,run["run_id"],core_config=(core_port,token))
    result["stored_evidence"]=stored["stored_evidence"]
    return result
