"""ACME-only curated RAG reference corpus; simulations explicitly identified.

This is a small versioned starting corpus, not a replacement for approved ACME
runbooks, incident records or a vector index.
"""
import re

DOCUMENTS = (
 {"id":"ACME-RB-SAN-001","title":"SAN dual fabric — diagnostic",
  "ci_ids":["ACME-SAN-FABRIC-A","ACME-SAN-FABRIC-B","ACME-STO-PURE01"],
  "text":"Compare both fabrics independently: switch port CRC/discards, FLOGI, zoning and link resets. Validate initiator-to-target paths and storage host mappings. Do not infer SAN causality from application latency alone. No zoning changes without HITL approval.",
  "synthetic":True,"status":"DEMO_REFERENCE"},
 {"id":"ACME-RB-RHEL-002","title":"RHEL multipath — investigation",
  "ci_ids":["ACME-SRV-RHEL01","ACME-SRV-RHEL02"],
  "text":"Collect multipath -ll, path state, kernel journal, dm-multipath counters and latency/queue depths. Correlate timestamps with switch-port errors and storage metrics. Read-only diagnostics first; avoid path changes without human approval.",
  "synthetic":True,"status":"DEMO_REFERENCE"},
 {"id":"ACME-RB-PAY-003","title":"Payment Processing — impact métier",
  "ci_ids":["ACME-SVC-PAYMENTS","ACME-APP-ORACLEPAY","ACME-APP-PORTAL"],
  "text":"Measure payment response latency p50/p95/p99, error rate, transaction volume and service dependencies before assigning severity or causality. Distinguish observed metrics from hypotheses. Link findings and changes to GLPI incident and change records when verified.",
  "synthetic":True,"status":"DEMO_REFERENCE"},
 {"id":"ACME-RB-GOV-004","title":"HITL et traçabilité ITIL 4",
  "ci_ids":["ACME-SVC-PAYMENTS"],
  "text":"HITL requires authenticated approver, explicit scoped action, reason, approval expiry, immutable audit receipt and precondition recheck. Link incident, affected CI, impact, urgency, assigned group, updates, resolution evidence and closure to the verified GLPI ticket. Never manufacture a GLPI ticket ID.",
  "synthetic":True,"status":"DEMO_REFERENCE"},
)

def retrieve(question, limit=3, ci_id=None):
    """Lexical retriever on local ACME corpus only; no outside knowledge."""
    terms=set(re.findall(r"[a-z0-9]{3,}",question.casefold()))
    if not terms:
        return []
    results=[]
    for d in DOCUMENTS:
        if ci_id and ci_id not in d["ci_ids"]:
            continue
        body=(d["title"]+" "+d["text"]+" "+" ".join(d["ci_ids"])).casefold()
        score=sum(1 for token in terms if token in body)
        if score:
            results.append((score,d))
    results.sort(key=lambda pair:(-pair[0],pair[1]["id"]))
    return [{"id":d["id"],"title":d["title"],"excerpt":d["text"],
             "ci_ids":d["ci_ids"],"synthetic":d["synthetic"],
             "status":d["status"],"score":score}
            for score,d in results[:max(0,min(limit,5))]]
