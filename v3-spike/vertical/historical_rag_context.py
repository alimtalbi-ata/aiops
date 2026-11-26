"""E22 historical RAG reference boundary; no document text sent to models.
Only use server-verified E16 history and the dedicated EnterpriseClock.
No caller-supplied scope, documents, tick, Evidence or provider configuration.
"""
import re
from enterprise_context import digest,DOCUMENTS
from historical_analyst_critic import assess
from enterprise_hybrid import METHOD

MAX_CONTEXT_BYTES=65536
SCORE_FIELDS={"bm25_score","vector_cosine","rrf_score"}
def build(history,clock,*,approved_excerpts=False):
    if type(approved_excerpts) is not bool:raise ValueError("invalid excerpt mode")
    baseline=assess(history)
    if baseline["analyst"]["candidates_truncated"]:raise ValueError("partial correlation")
    runs={}
    for group in history["groups"]:
        resource=group["resource"]
        for signal in group["signals"]:
            for ref in signal["evidence_refs"]:
                rid=ref["run_id"]
                if rid not in history["run_ids"]:raise ValueError("foreign run")
                if rid in runs and runs[rid]["resource"]!=resource:raise ValueError("ambiguous run resource")
                entry=runs.setdefault(rid,{"resource":resource,"evidence_ids":set()})
                entry["evidence_ids"].add(ref["evidence_id"])
    if history["undated"] or set(runs)!=set(history["run_ids"]):
        raise ValueError("complete dated run context required")
    approved={d["id"]:d for d in DOCUMENTS}
    result={"classification":"SYNTHETIC_HISTORICAL_RAG_CONTEXT_E22",
            "correlation_sha256":baseline["analyst"]["correlation_sha256"],
            "graph_sha256":baseline["analyst"]["graph_sha256"],
            "retrieval_method":METHOD,"runs":[],"reference_text_included":False,
            "llm_inference_performed":False,"learned_embeddings":False,
            "causality_established":False,"root_cause":"UNKNOWN","confidence":None,
            "tenant_acl_qualified":False,"operational_decision":"DENY","production_authorized":False}
    for rid,entry in sorted(runs.items()):
        resource=entry["resource"]
        # Exact resource only, never potential impact, user/group scope or another run's scope.
        # Query is server-derived, no user instructions or raw signals.
        query=" ".join(resource.lower().split("-")[3:])+" triage runbook"
        docs=clock.historical_documents(rid,{resource},query)
        state=docs["state"]
        row={"run_id":rid,"resource":resource,"evidence_ids":sorted(entry["evidence_ids"]),
             "logical_tick":docs["logical_tick"],"catalog_sha256":None,"state":state,"references":[]}
        if state=="HISTORICAL_LOGICAL_VERSION":
            tick=docs["logical_tick"]
            catalog=docs["catalog_sha256"]
            if type(tick) is not int or tick<1 or not re.fullmatch("[a-f0-9]{64}",catalog):raise ValueError("invalid historical catalog")
            row["catalog_sha256"]=catalog
            seen=set()
            for channel in ("hybrid_retrieval","case_retrieval"):
                retrieval=docs[channel]
                if (retrieval["classification"]!="SYNTHETIC_HYBRID_RETRIEVAL_E9"
                    or retrieval["method"]!=METHOD or retrieval["logical_tick"]!=tick
                    or retrieval["query_sha256"]!=digest(query) or retrieval["operational_decision"]!="DENY"
                    or retrieval["production_authorized"] is not False or retrieval["llm_inference_performed"] is not False
                    or len(retrieval["citations"])>5):raise ValueError("invalid historical retrieval")
                for citation in retrieval["citations"]:
                    raw={k:v for k,v in citation.items() if k not in SCORE_FIELDS|{"sha256"}}
                    ident=citation["id"]
                    if (not isinstance(ident,str) or not re.fullmatch("[A-Z0-9-]{1,120}",ident)
                        or citation["tenant"]!="synthetic-demo" or citation["observed_evidence"] is not False
                        or citation.get("production_authorized",False) is not False
                        or resource not in citation["scope"] or type(citation["valid_from_tick"]) is not int
                        or not 1<=citation["valid_from_tick"]<=tick or type(citation["version"]) is not int
                        or citation["version"]<1 or digest(raw)!=citation["sha256"] or ident in seen
                        or ident in entry["evidence_ids"]):raise ValueError("invalid or out-of-scope reference")
                    seen.add(ident)
                    ref={"reference_id":ident,"version":citation["version"],
                      "sha256":citation["sha256"],"valid_from_tick":citation["valid_from_tick"],
                      "retrieval_channel":channel,"observed_evidence":False}
                    # Only immutable, checked-in synthetic runbook text, never arbitrary
                    # retrieved text, generated incident narratives or case history.
                    doc=approved.get(ident)
                    if (approved_excerpts and doc and channel=="hybrid_retrieval"
                        and citation.get("provenance")=="SYNTHETIC_REFERENCE_ONLY"
                        and citation["scope"]==doc["scope"] and citation["title"]==doc["title"]
                        and citation["text"]==doc["text"] and citation["version"]==1):
                        ref["approved_excerpt"]=doc["text"]
                    row["references"].append(ref)
        elif state not in ("UNBOUND_LEGACY","PRE_E7_UNAVAILABLE"):
            raise ValueError("unknown historical state")
        result["runs"].append(row)
    result["reference_count"]=sum(len(r["references"]) for r in result["runs"])
    if approved_excerpts:
        result["classification"]="SYNTHETIC_APPROVED_RAG_EXCERPTS_E24"
        result["reference_text_included"]=any("approved_excerpt" in c for r in result["runs"] for c in r["references"])
    result["state"]="REFERENCES_ONLY" if result["reference_count"] else "NO_REFERENCES"
    import json
    if len(json.dumps(result,separators=(",",":")).encode())>MAX_CONTEXT_BYTES:raise ValueError("context too large")
    result["context_sha256"]=digest(result)
    return result
