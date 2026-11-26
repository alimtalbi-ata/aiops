"""Correlate only verified, bounded historical DEMO signal references."""
import re
from collections import defaultdict
from enterprise_correlation import preview
from ingestion_demo import ingest
from evidence_retrieval import validated_reference

def reconstruct(signal,resource):
    if not isinstance(signal,dict) or not {"event_id","source","sha256"}<=set(signal) or set(signal)-{"event_id","source","sha256","enterprise","observation"}:
        raise ValueError("invalid stored signal")
    kind,source=signal["source"].split(":",1)
    row={"id":signal["event_id"],"kind":kind,"source":source,"resource":resource,
         "tenant":"synthetic-demo","synthetic":True}
    for k in ("enterprise","observation"):
        if k in signal:row[k]=signal[k]
    # The legacy normalized evidence omits severity; recover it only by exact
    # reproduction of the stored canonical signal digest, never by inference.
    matches=[]
    for severity in ("warning","critical"):
        candidate={**row,"severity":severity}
        if ingest([candidate])["incidents"][0]["evidence"][0]==signal:
            matches.append(candidate)
    if len(matches)!=1: raise ValueError("stored signal cannot be reproduced")
    return matches[0]

def historical_preview(run_ids,window_seconds,graph,load):
    if (not isinstance(run_ids,list) or not 2<=len(run_ids)<=5
        or any(not isinstance(r,str) or not re.fullmatch(r"RUN-[A-F0-9]{16}",r) for r in run_ids)
        or len(set(run_ids))!=len(run_ids)):
        raise ValueError("2–5 distinct synthetic ingestion runs required")
    if type(window_seconds) is not int or not 1<=window_seconds<=3600:raise ValueError("invalid window")
    rows=[]
    refs=defaultdict(list)
    evidence_ids=set()
    for rid in sorted(run_ids):
        core,details=load(rid)
        run=core["run"]
        if (run["run_id"]!=rid or run["mode"]!="DEMO"
            or not re.fullmatch(r"INC-CI-INGEST-[a-f0-9]{32}",run["incident_id"])
            or details["run_id"]!=rid or details["classification"]!="SYNTHETIC_LAB_CONTEXT"
            or details["production_authorized"] is not False):
            raise ValueError("invalid historical binding")
        items=details["verified_signals"]
        # The existing evidence endpoint reads at most 20. Fail closed at
        # that boundary rather than silently correlate a potentially truncated run.
        if not isinstance(items,list) or not 1<=len(items)<20:
            raise ValueError("complete bounded evidence required")
        expected={r["evidence_id"]:r["payload_hash"] for r in details["evidence"]}
        if len(expected)!=len(items):raise ValueError("incomplete evidence projection")
        for item in items:
            ref=validated_reference(item)
            eid=ref["evidence_id"]
            if eid in evidence_ids or expected.get(eid)!=ref["payload_hash"]:
                raise ValueError("ambiguous evidence identity")
            evidence_ids.add(eid)
            signal=item["signal"]
            rows.append(reconstruct(signal,details["root"]))
            refs[(signal["event_id"],signal["sha256"])].append({**ref,"run_id":rid,"incident_id":run["incident_id"]})
    result=preview(rows,graph,window_seconds)
    def attach(item):
        source=refs[(item["event_id"],item["sha256"])]
        if not source:raise ValueError("missing evidence source")
        return {**item,"evidence_refs":sorted(source,key=lambda r:(r["run_id"],r["evidence_id"]))}
    for group in result["groups"]:
        group["signals"]=[attach(s) for s in group["signals"]]
    result["undated"]=[attach(s) for s in result["undated"]]
    return {**result,"classification":"SYNTHETIC_HISTORICAL_CORRELATION_PREVIEW",
            "run_ids":sorted(run_ids),"verified_evidence_count":len(evidence_ids),
            "tenant_acl_qualified":False}
