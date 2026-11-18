from copy import deepcopy
from hashlib import sha256
from portal.acme_runtime_context import qualify_context, digest
from portal.acme_authority_readers import collect_prepared
from worker.acme_simulated_hitl import verify_no_effect_receipt
from worker.int06a_contract import IDENTITY, validate_postcheck, validate_manifest, utc

def exercise(expected,intent,readers,policies,registry,clock,m,o,expected_sha):
    rows={}
    def capture(k):
        row=deepcopy(readers[k]())
        rows.setdefault(k,[]).append(row)
        return row
    b=collect_prepared(expected,intent,{k:lambda k=k:capture(k) for k in readers},policies,as_of_utc=clock,source_registry=registry)
    result=dict(b=b,c=None,runtime_attested=False,finish_authorized=False,resolution_authorized=False,go=False)
    if b["reason"]!="INJECTED_READBACKS_NOT_ATTESTED" or b["qualification"]!="BLOCK":
        return result
    if b!=qualify_context(expected,intent,{k:v[0] for k,v in rows.items()},policies,as_of_utc=clock,source_registry=registry):
        raise ValueError("B divergence")
    core,twin=rows["core"][0]["content"],rows["twin"][0]["content"]
    receipt=m["worker_receipt"]
    identity={k:intent[k] for k in IDENTITY}
    if not verify_no_effect_receipt(receipt,identity): raise ValueError("receipt")
    if type(receipt["effect_receipts"]) is not int or receipt["effect_receipts"]!=0: raise ValueError("count")
    if (receipt["core_request_sha256"]!=core["request_sha256"] or receipt["core_source_event_ids"]!=core["source_event_ids"] or receipt["twin_approval_nonce_sha256"]!=sha256(twin["approval_nonce"].encode("ascii")).hexdigest()): raise ValueError("prepared binding")
    h,p,t,r=(o[k] for k in ("history","postcheck","terminal","terminal_readback"))
    if any(x["identity"]!=identity or x["prepared_snapshot"]!=expected["snapshot_id"] or x["impact_incident_id"]!=expected["impact_incident_id"] for x in (h,p,t,r)): raise ValueError("identity")
    if h["receipt_sha256"]!=receipt["receipt_sha256"] or p["history_sha256"]!=digest(h) or t["postcheck_sha256"]!=digest(p) or r!=t or t["snapshot_id"]==expected["snapshot_id"] or type(t["version"]) is not int or t["version"]<=core["version"]: raise ValueError("continuity")
    times=[utc(x["observed_at"]) for x in (rows["core"][0],h,p,t)]
    if not all(a<b for a,b in zip(times,times[1:])) or times[-1]>utc(clock): raise ValueError("time")
    i=o["independent"]
    if i["history_sha256"]!=digest(h) or i["worker_receipt_sha256"]!=h["receipt_sha256"] or i["terminal"]!=t or i["terminal_readback_sha256"]!=digest(r) or p["verified"] is not True: raise ValueError("readback")
    post=validate_postcheck(intent=intent,independently_read=i)
    v=validate_manifest(m,expected_sha=expected_sha,intent=intent,independently_read=i)
    if post["finish_authorized"] is not False or v["resolution_authorized"] is not False or v["runtime_attested"] is not False: raise ValueError("authority")
    return dict(result,c=v,postcheck=post)
