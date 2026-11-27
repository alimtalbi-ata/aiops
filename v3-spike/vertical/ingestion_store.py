"""Synthetic lab persistence; partial writes are retryable, not transactional."""
import hashlib
import json
from bounded_http_transport import post_legacy_evidence_json
from evidence_retrieval import validated_reference
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
    seen=set()
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
            receipt=validated_reference(post_legacy_evidence_json(port,body))
            if receipt["payload_hash"]!=digest or receipt["evidence_id"] in seen:
                raise ValueError("Unverified receipt")
            seen.add(receipt["evidence_id"])
            receipts.append(receipt)
    result["stored_evidence"]=receipts
    return result
