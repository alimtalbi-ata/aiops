"""Bounded read-only Copilot projection from verified synthetic lab context."""
def answer(core, context):
    run=core["run"]
    if (core.get("production_authorized") is not False
        or context.get("classification")!="SYNTHETIC_LAB_CONTEXT"
        or context.get("production_authorized") is not False
        or run["run_id"]!=context["run_id"]
        or context.get("policy")!="DENY"):
        raise ValueError("unverified context")
    sources=[{"evidence_id":e["evidence_id"],"payload_hash":e["payload_hash"]} for e in context["evidence"]]
    return {"classification":"SYNTHETIC_COPILOT_CONTEXT",
            "incident_id":run["incident_id"],"run_id":run["run_id"],
            "answer":f"Incident {run['incident_id']}: {len(context['affected'])} topology nodes in scope; {len(sources)} verified evidence records. Root cause UNKNOWN. Operational action DENY.",
            "sources":sources,"confidence":None,"root_cause":"UNKNOWN",
            "operational_decision":"DENY","production_authorized":False}
