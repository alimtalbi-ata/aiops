"""Deterministic E18 assessment over server-verified E16 history, not LLM/RCA.
Only call with historical_preview output from the trusted service boundary.
A matching Critic projection is not independent QA or independent source proof.
"""
from enterprise_context import digest
from evidence_retrieval import validated_reference
from enterprise_correlation import timestamp

def _refs(group, run_ids):
    refs=[]
    for signal in group["signals"]:
        for item in signal["evidence_refs"]:
            ref=validated_reference(item)
            if item["run_id"] not in run_ids:
                raise ValueError("foreign historical run")
            refs.append({**ref,"run_id":item["run_id"],"incident_id":item["incident_id"],
                         "event_id":signal["event_id"],"signal_sha256":signal["sha256"],
                         "source":signal["source"],"occurred_at":signal["occurred_at"]})
    if not refs or len({r["evidence_id"] for r in refs})!=len(refs):
        raise ValueError("missing or duplicate historical provenance")
    return sorted(refs,key=lambda r:(r["run_id"],r["evidence_id"]))

def analyze(history):
    if (history.get("classification")!="SYNTHETIC_HISTORICAL_CORRELATION_PREVIEW"
        or history.get("tenant")!="synthetic-demo" or history.get("production_authorized") is not False
        or history.get("causality_established") is not False or history.get("incidents_created") is not False
        or history.get("tenant_acl_qualified") is not False or history.get("operational_decision")!="DENY"):
        raise ValueError("unverified historical projection")
    run_ids=history["run_ids"]
    groups={g["candidate_group_id"]:g for g in history["groups"]}
    if len(groups)!=len(history["groups"]):
        raise ValueError("ambiguous candidate group")
    hypotheses=[]
    for link in history["candidates"]:
        dependent=groups[link["dependent_group_id"]]
        dependency=groups[link["dependency_group_id"]]
        if (link["dependent_resource"]!=dependent["resource"] or link["dependency_resource"]!=dependency["resource"]
            or link["relationship"]!="TEMPORAL_DEPENDENCY_CANDIDATE_NOT_CAUSAL_PROOF" or not link["path"]):
            raise ValueError("invalid candidate binding")
        de=_refs(dependent,run_ids)
        dy=_refs(dependency,run_ids)
        if not any(a["run_id"]!=b["run_id"] for a in de for b in dy):
            continue
        if timestamp(dependency["last_at"])<timestamp(dependent["first_at"]):
            order="DEPENDENCY_OBSERVED_FIRST"
        elif timestamp(dependency["first_at"])>timestamp(dependent["last_at"]):
            order="DEPENDENT_OBSERVED_FIRST"
        else:
            order="OVERLAPPING_OR_SIMULTANEOUS"
        hypotheses.append({"hypothesis_id":"HC-"+digest([history["graph_sha256"],link])[:24],
                           "candidate":link,"temporal_order":order,"dependent_evidence":de,"dependency_evidence":dy,
                           "root_cause":"UNKNOWN","confidence":None,"independent_sources_verified":False,
                           "causality_established":False})
    return {"classification":"SYNTHETIC_HISTORICAL_RULE_BASED_ANALYST","correlation_sha256":digest(history),
            "graph_sha256":history["graph_sha256"],"run_ids":run_ids,
            "state":"CANDIDATES_ONLY" if hypotheses else ("PARTIAL_NO_CANDIDATE" if history["candidates_truncated"] else "UNKNOWN"),
            "hypotheses":hypotheses,"candidates_truncated":history["candidates_truncated"],
            "root_cause":"UNKNOWN","confidence":None,"llm_inference_performed":False,
            "production_authorized":False}

def critique(proposed, history):
    expected=analyze(history)
    matches=proposed==expected
    limitations=["NO_CAUSAL_PROOF","NO_INDEPENDENT_SOURCE_VERIFICATION","RULE_BASED_NOT_INDEPENDENT_QA"]
    if history["candidates_truncated"]:
        limitations.append("CANDIDATES_TRUNCATED")
    checks=[]
    if matches:
        for h in expected["hypotheses"]:
            order=h["temporal_order"]
            checks.append({"hypothesis_id":h["hypothesis_id"],"evidence_bound":True,
                           "temporal_assessment":("COMPATIBLE_NOT_PROOF" if order=="DEPENDENCY_OBSERVED_FIRST" else
                              "REVERSE_ORDER_CHALLENGE" if order=="DEPENDENT_OBSERVED_FIRST" else "ORDER_UNRESOLVED"),
                           "causality_established":False})
    return {"classification":"SYNTHETIC_HISTORICAL_RULE_BASED_CRITIC","projection_matches":matches,
            "checks":checks,"limitations":limitations,"root_cause":"UNKNOWN","confidence":None,
            "causality_established":False,"operational_decision":"DENY","production_authorized":False}

def assess(history):
    analysis=analyze(history)
    return {"classification":"SYNTHETIC_HISTORICAL_ASSESSMENT","analyst":analysis,
            "critic":critique(analysis,history),"incidents_created":False,"tenant_acl_qualified":False,
            "operational_decision":"DENY","production_authorized":False}
