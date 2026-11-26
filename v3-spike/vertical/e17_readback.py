"""Server-side E17 projection from real Core/Worker and independent Evidence.

No caller-supplied receipt, hash, samples or scope. The only inputs are two
selected run identities, both re-read via the existing verified lab context.
"""
import http.client
import json
import re
from recovery_verify import digest,verify_recovery
from lab_context import dynamic_context

RUN=r"RUN-[A-F0-9]{16}"
SCOPE=["NODE-CI-ROOT","NODE-CI-ENT-ASSET-PAR","NODE-CI-ENT-APP-PAY"]


def read_worker_receipt(port,token,rid):
    if (type(port) is not int or not 1024<=port<=65535 or port in (7770,7777,7790)
        or not isinstance(token,str) or not 32<=len(token)<=256 or not token.isascii()
        or any(not 33<=ord(c)<=126 for c in token) or not re.fullmatch(RUN,rid)):
        raise ValueError("invalid isolated Core config")
    conn=http.client.HTTPConnection("127.0.0.1",port,timeout=20)
    try:
        conn.request("GET","/api/noc/runs/"+rid+"/e17-receipt",
                     headers={"Authorization":"Bearer "+token,"Accept":"application/json"})
        response=conn.getresponse()
        raw=response.read(65537)
        if response.status!=200 or len(raw)>65536:
            raise ValueError("verified Worker receipt unavailable")
        return json.loads(raw)
    finally:
        conn.close()


def project_recovery(*,read_context,read_receipt,original_run_id,comparison_run_id):
    if (not all(isinstance(v,str) and re.fullmatch(RUN,v) for v in (original_run_id,comparison_run_id))
        or original_run_id==comparison_run_id):
        raise ValueError("distinct selected runs required")
    before,original=read_context(original_run_id)
    _,comparison=read_context(comparison_run_id)
    projection=read_receipt(original_run_id)
    receipt=projection["action_receipt"]
    if (projection.get("classification")!="V3_E17_WORKER_RECEIPT_READBACK"
        or projection.get("run_id")!=original_run_id
        or projection.get("operational_decision")!="DENY"
        or projection.get("production_authorized") is not False
        or projection.get("core_business_stages_qualified") is not False
        or type(projection.get("activities_completed")) is not int or projection["activities_completed"]!=1
        or type(projection.get("history_events")) is not int or not 5<=projection["history_events"]<=64
        or projection.get("action_receipt_sha256")!=digest(receipt)
        or receipt["binding"]["incident_id"]!=before["run"]["incident_id"]):
        raise ValueError("invalid Worker receipt projection")
    def read_action_receipt(receipt_id):
        if receipt_id!=receipt["receipt_id"]:
            raise ValueError("unknown receipt")
        return receipt
    verified=verify_recovery(read_context=read_context,read_action_receipt=read_action_receipt,
        original_run_id=original_run_id,comparison_run_id=comparison_run_id,scope=SCOPE,
        original_refs=original["evidence"],comparison_refs=comparison["evidence"],
        action_receipt_id=receipt["receipt_id"],action_receipt_sha256=projection["action_receipt_sha256"])
    return {"classification":"SYNTHETIC_GAMMA_E17_VERIFIED_READBACK",
            "worker":projection,"verification":verified,
            "operational_decision":"DENY","production_authorized":False,
            "tenant_acl_qualified":False,"core_business_stages_qualified":False}


def dynamic_recovery(core_port,token,twin_port,evidence_port,node,original,comparison):
    def context(rid):
        return dynamic_context(core_port,token,rid,twin_port,evidence_port,node,
                               include_signals=True,multiasset=True)
    return project_recovery(read_context=context,
                            read_receipt=lambda rid:read_worker_receipt(core_port,token,rid),
                            original_run_id=original,comparison_run_id=comparison)
