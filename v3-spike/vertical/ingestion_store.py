"""Synthetic lab persistence; partial writes are retryable, not transactional."""
import hashlib
import json
from urllib.request import Request,urlopen
from ingestion_demo import ingest

def persist(records,port,run_id,*,core_config=None):
    result=ingest(records)
    if type(port) is not int or not 1024<=port<=65535 or port in (7770,7777,7790):
        raise ValueError("Invalid lab port")
    canonical_incident = None
    if core_config is not None:
        from core_read import read_run
        verified=read_run(*core_config,run_id)["run"]
        if len(result["incidents"]) != 1:
            raise ValueError("One correlated incident required")
        batch_digest=hashlib.sha256(json.dumps(result["incidents"][0],sort_keys=True,separators=(",",":")).encode()).hexdigest()
        canonical_incident="INC-CI-INGEST-"+batch_digest[:32]
        if verified["mode"]!="DEMO" or verified["incident_id"]!=canonical_incident:
            raise ValueError("Verified ingestion batch binding required")
    elif not isinstance(run_id,str) or not run_id.startswith("RUN-CI-"):
        raise ValueError("Synthetic run required")
    receipts=[]
    for incident in result["incidents"]:
        for event in incident["evidence"]:
            payload={"run_id":run_id,"incident_id":canonical_incident or incident["id"],"signal":event}
            if canonical_incident is not None:
                payload["correlation_id"]=incident["id"]
                payload["resource"]=incident["resource"]
            digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
            body={"source":"v3-synthetic-ingestion","external_id":event["event_id"],
                  "claim":"Normalized synthetic signal","confidence":0.0,
                  "provenance":{"synthetic":True,"run_id":run_id},"payload":payload}
            req=Request(f"http://127.0.0.1:{port}/api/evidence",data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
            with urlopen(req,timeout=5) as response:
                raw=response.read(65537)
                if len(raw)>65536: raise ValueError("Oversized receipt")
                receipt=json.loads(raw)
            if receipt.get("payload_hash")!=digest or not isinstance(receipt.get("evidence_id"),str) or not receipt["evidence_id"]:
                raise ValueError("Unverified receipt")
            receipts.append({"evidence_id":receipt["evidence_id"],"payload_hash":digest})
    result["stored_evidence"]=receipts
    return result
