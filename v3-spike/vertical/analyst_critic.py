"""Deterministic synthetic POC; not an LLM or causal inference engine."""
def analyze(context):
    if context.get("classification")!="SYNTHETIC_LAB_CONTEXT" or context.get("production_authorized") is not False:
        raise ValueError("unverified context")
    sources=sorted({e["evidence_id"] for e in context["evidence"]})
    return {"classification":"SYNTHETIC_RULE_BASED_ANALYST","hypothesis":"INCIDENT_OBSERVED" if sources else "UNKNOWN","evidence_ids":sources,"root_cause":"UNKNOWN","confidence":None}

def critique(analysis, context):
    analyze(context)
    verified={e["evidence_id"] for e in context["evidence"]}
    supported=set(analysis["evidence_ids"])<=verified and bool(analysis["evidence_ids"])
    return {"classification":"SYNTHETIC_RULE_BASED_CRITIC","evidence_supported":supported,"causality_established":False,"root_cause":"UNKNOWN","confidence":None,"operational_decision":"DENY","production_authorized":False}
