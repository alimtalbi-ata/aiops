"""Offline projection of INT07 collector results, not an authority verifier."""
from html import escape
import re

def render_collector_result(result=None):
    def text(v):
        return escape(v) if isinstance(v,str) and 0<len(v)<=512 else "MISSING"
    def item(k,v):
        return "<dt>"+escape(k)+"</dt><dd>"+text(v)+"</dd>"
    valid = isinstance(result,dict) and (
        result.get("schema")=="aiops.acme.runtime-context.v1"
        and result.get("scope")=="RUNTIME_SANDBOX"
        and result.get("binding_status")=="UNBOUND"
        and result.get("runtime_freshness")=="UNKNOWN"
        and result.get("qualification") in ("BLOCK","REJECT")
        and all(result.get(k) is False for k in (
        "runtime_attested","live_remediation_authorized","go",
        "finish_authorized","resolution_authorized")))
    reason = result.get("reason") if valid else None
    status = ("UNKNOWN — BLOCK" if result["qualification"]=="BLOCK" else
              "REJECT — refus de qualification") if valid else ("MISSING" if result is None else "UNKNOWN — projection incompatible")
    coherent = valid and result["qualification"]=="BLOCK" and reason=="OFFLINE_CONTINUITY_CONSISTENT_NOT_ATTESTED"
    context = result.get("context") if coherent else None
    context = context if isinstance(context,dict) else {}
    parts=["<section class='story-context' aria-label='Résultat collecteur offline'>",
           "<h3>RUNTIME_SANDBOX — UNBOUND</h3>",
           "<p>STORY_OFFLINE / SIMULATED : contexte distinct.</p>",
           "<p>Admission : MISSING — projection B attendue.</p>",
           "<p>Préterminal : MISSING — projection B attendue.</p>",
           "<h4>Qualification finale</h4><p>"+escape(status)+" — "+text(reason)+"</p>",
           "<p>CONTRACT_ONLY — cohérence offline, aucune exécution attestée.</p>" if coherent else "<p>Contrat terminal : MISSING ou UNKNOWN.</p>",
           "<details><summary>Identités et provenance disponibles — non attestées</summary><dl>"]
    for k in ("tenant_id","incident_id","impact_incident_id","run_id","attempt_id","snapshot_id","proposal_id","ticket_id","approval_id"):
        parts.append(item(k,context.get(k) if k not in ("proposal_id","ticket_id","approval_id") else None))
    parts.append(item("Fraîcheur runtime","UNKNOWN"))
    parts.append("</dl><h4>Provenance injectée — intégrité, pas attestation</h4>")
    evidence=result.get("evidence") if coherent else None
    if isinstance(evidence,list) and len(evidence)<=3:
        for row in evidence:
            if not isinstance(row,dict): continue
            parts.append("<dl>")
            for k in ("authority","source_id","source_ref","observed_at","snapshot_id","content_sha256"):
                v=row.get(k)
                if k=="content_sha256" and (not isinstance(v,str) or not re.fullmatch("[0-9a-f]{64}",v)): v=None
                parts.append(item(k,v))
            parts.append("</dl>")
    else: parts.append("<p>MISSING</p>")
    parts.append("</details><p>Qualification runtime : UNKNOWN. PROD / LIVE : NO-GO. Aucun ACK ni effet attesté.</p></section>")
    return "".join(parts)
