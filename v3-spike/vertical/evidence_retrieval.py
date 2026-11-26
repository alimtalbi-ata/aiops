"""Run-scoped structured retrieval over the verified lab projection, not LLM inference."""
import re

def validated_reference(item):
    """Validate reference format, not authenticity (checked by lab_context)."""
    if not isinstance(item,dict):
        raise ValueError("invalid evidence reference")
    eid=item.get("evidence_id")
    digest=item.get("payload_hash")
    if (not isinstance(eid,str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}",eid)
        or not isinstance(digest,str) or not re.fullmatch(r"[a-f0-9]{64}",digest)):
        raise ValueError("invalid evidence reference")
    return {"evidence_id":eid,"payload_hash":digest}

def index_references(items):
    if not isinstance(items,list) or len(items)>20:
        raise ValueError("invalid evidence corpus")
    indexed={}
    for item in items:
        ref=validated_reference(item)
        eid=ref["evidence_id"]
        if eid in indexed:
            raise ValueError("duplicate evidence reference")
        indexed[eid]=ref
    return indexed

def retrieve(core, context, topic="rca", *, limit=5):
    run=core["run"]
    if (core.get("production_authorized") is not False
        or context.get("classification")!="SYNTHETIC_LAB_CONTEXT"
        or context.get("production_authorized") is not False
        or context.get("policy")!="DENY"
        or run["run_id"]!=context.get("run_id")
        or run.get("mode","DEMO") not in ("DEMO","REPLAY","STORY")):
        raise ValueError("unverified retrieval scope")
    if topic not in ("rca","evidence") or type(limit) is not int or not 1<=limit<=20:
        raise ValueError("invalid retrieval request")
    indexed=index_references(context["evidence"])
    if topic=="rca":
        model=context.get("diagnosis")
        selected=[]
        if model is not None:
            if (model.get("classification")!="SYNTHETIC_MODEL_ONLY"
                or model.get("root_cause")!="UNKNOWN" or model.get("confidence") is not None
                or model.get("operational_decision")!="DENY" or model.get("executed_on_host") is not False):
                raise ValueError("unverified diagnosis")
            selected=model["evidence_ids"]
            if (not isinstance(selected,list) or any(not isinstance(x,str) or x not in indexed for x in selected)
                or len(set(selected))!=len(selected)):
                raise ValueError("diagnosis cites unbound evidence")
        reason="MODEL_OBSERVATION_REFERENCE"
    else:
        selected=sorted(indexed)
        reason="RUN_SCOPED_EVIDENCE_REFERENCE"
    matches=[{**indexed[eid],"reason":reason} for eid in selected[:limit]]
    return {"classification":"SYNTHETIC_STRUCTURED_RETRIEVAL","run_id":run["run_id"],
            "incident_id":run["incident_id"],"topic":topic,"state":"MATCHED" if matches else "UNKNOWN",
            "matches":matches,"match_count":len(selected),"truncated":len(selected)>limit,
            "llm_inference_performed":False,"causality_established":False,
            "operational_decision":"DENY","production_authorized":False}
