"""Bounded read-only Copilot projection from verified synthetic lab context."""
from analyst_critic import analyze, critique
from evidence_retrieval import retrieve

def answer(core, context, *, topic="rca"):
    run=core["run"]
    if (core.get("production_authorized") is not False
        or context.get("classification")!="SYNTHETIC_LAB_CONTEXT"
        or context.get("production_authorized") is not False
        or run["run_id"]!=context["run_id"]
        or context.get("policy")!="DENY"):
        raise ValueError("unverified context")
    sources=[{"evidence_id":e["evidence_id"],"payload_hash":e["payload_hash"]} for e in context["evidence"]]
    retrieval=retrieve(core,context,topic)
    analysis=analyze(context)
    criticism=critique(analysis,context)
    return {"retrieval":retrieval,"analysis":analysis,"criticism":criticism,"classification":"SYNTHETIC_COPILOT_CONTEXT",
            "incident_id":run["incident_id"],"run_id":run["run_id"],
            "answer":f"Incident {run['incident_id']}: {len(context['affected'])} topology nodes in scope; {len(sources)} verified evidence records. Root cause UNKNOWN. Operational action DENY.",
            "sources":sources,"confidence":None,"root_cause":"UNKNOWN",
            "operational_decision":"DENY","production_authorized":False}
