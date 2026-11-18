"""Offline projection of INT07 collector results, not an authority verifier."""
from html import escape
import re

def render_collector_result(result=None, *, admission=None, preterminal=None):
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
           render_hitl_inbox(admission),
           render_phase_identity_comparison(admission, preterminal),
           render_phase("Admission", "ADMISSION", admission),
           render_phase("Préterminal", "PRETERMINAL", preterminal),
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

def render_phase(label, phase, value=None):
    """Display B results separately; never infer continuity or grant authority."""
    prefix = "<p>"+escape(label)+" : "
    if value is None:
        return prefix+"MISSING — projection B attendue.</p>"
    if not (isinstance(value,dict) and value.get("schema")=="aiops.int08.phase.v1"
            and value.get("phase")==phase and value.get("qualification") in ("BLOCK","REJECT")
            and value.get("binding_status")=="UNBOUND" and value.get("runtime_freshness")=="UNKNOWN"
            and all(value.get(k) is False for k in ("runtime_attested","execution_allowed",
                "finish_authorized","resolution_authorized","live_remediation_authorized"))):
        return prefix+"UNKNOWN — projection incompatible.</p>"
    def safe(v):
        return escape(v) if isinstance(v,str) and 0<len(v)<=512 else "MISSING"
    reason=value.get("reason")
    coherent=(value["qualification"]=="BLOCK" and value.get("contract_status")=="CONTRACT_ONLY"
              and reason==phase+"_CONSISTENT_NOT_ATTESTED")
    parts=[prefix+safe(value["qualification"])+" — UNKNOWN — "+safe(reason)+"</p>"]
    if coherent:
        projection=value.get("projection")
        if not (isinstance(projection,dict) and projection.get("binding_status")=="UNBOUND"
                and projection.get("runtime_freshness")=="UNKNOWN" and projection.get("runtime_attested") is False):
            return prefix+"UNKNOWN — projection incompatible.</p>"
        parts.append("<details><summary>"+escape(label)+" — CONTRACT_ONLY, provenance non attestée</summary><dl>")
        identity=projection.get("identity")
        if isinstance(identity,dict):
            for k in ("tenant_id","incident_id","run_id","attempt_id","proposal_id","ticket_id","approval_id"):
                parts.append("<dt>"+k+"</dt><dd>"+safe(identity.get(k))+"</dd>")
        parts.append("<dt>impact_incident_id</dt><dd>"+safe(projection.get("impact_incident_id"))+"</dd></dl>")
        rows=projection.get("provenance")
        if isinstance(rows,list) and len(rows)<=8:
            for row in rows:
                if not isinstance(row,dict): continue
                parts.append("<dl>")
                for k in ("role","source_id","observed_at","content_sha256","classification"):
                    v=row.get(k)
                    if k=="content_sha256" and not (isinstance(v,str) and re.fullmatch("[0-9a-f]{64}",v)): v=None
                    parts.append("<dt>"+k+"</dt><dd>"+safe(v)+"</dd>")
                parts.append("</dl>")
        parts.append("</details>")
    return "".join(parts)


def render_phase_identity_comparison(admission, preterminal):
    """Compare display identities only; never infer phase continuity or order."""
    def identity(value, phase):
        if not isinstance(value, dict) or value.get("contract_status") != "CONTRACT_ONLY":
            return None
        if "projection incompatible" in render_phase(phase, phase, value):
            return None
        if value.get("qualification") != "BLOCK" or value.get("reason") != phase+"_CONSISTENT_NOT_ATTESTED":
            return None
        projection = value.get("projection")
        ident = projection.get("identity") if isinstance(projection, dict) else None
        if not isinstance(ident, dict):
            return None
        fields = tuple(ident.get(k) for k in ("tenant_id","incident_id","run_id","attempt_id","proposal_id","ticket_id","approval_id")) + (projection.get("impact_incident_id"),)
        return fields if all(isinstance(v,str) and 0<len(v)<=512 for v in fields) else None
    a, p = identity(admission,"ADMISSION"), identity(preterminal,"PRETERMINAL")
    state = "MISSING" if admission is None or preterminal is None else "UNKNOWN"
    if a is not None and p is not None:
        state = "Identités déclarées concordantes" if a == p else "UNKNOWN — identités divergentes"
    return "<p>Comparaison admission / préterminal : "+state+" ; continuité causale UNKNOWN, aucune fusion des historiques.</p>"


def render_hitl_inbox(admission=None):
    """Historical #194 presentation only; no IAM, transport or approval action."""
    proposal = None
    if (isinstance(admission, dict)
            and admission.get("contract_status") == "CONTRACT_ONLY"
            and admission.get("qualification") == "BLOCK"
            and admission.get("reason") == "ADMISSION_CONSISTENT_NOT_ATTESTED"
            and "projection incompatible" not in render_phase("Admission", "ADMISSION", admission)):
        projection = admission.get("projection")
        if isinstance(projection, dict):
            identity = projection.get("identity")
            if isinstance(identity, dict):
                candidate = identity.get("proposal_id")
                if isinstance(candidate, str) and 0 < len(candidate) <= 512:
                    proposal = candidate
    parts = ["<section aria-labelledby='hitl-inbox-title'><h4 id='hitl-inbox-title'>HITL Inbox — consultation offline</h4>",
             "<p>STORY_OFFLINE / CONTRACT_ONLY — aucune approbation ni exécution attestée. Ownership UNKNOWN / UNBOUND.</p>"]
    if proposal is None:
        parts.append("<p>Proposition UNKNOWN — aucune ligne qualifiée.</p>")
    else:
        parts.append("<dl><dt>Proposition déclarée</dt><dd>"+escape(proposal)+"</dd>"
                     "<dt>Risque</dt><dd>UNKNOWN</dd><dt>Action</dt><dd>UNKNOWN</dd>"
                     "<dt>CI cible</dt><dd>UNKNOWN</dd><dt>État HITL</dt><dd>UNKNOWN</dd>"
                     "<dt>Preuves</dt><dd>Voir la provenance Admission ci-dessous ; non attestée.</dd></dl>")
    parts.append("</section>")
    return "".join(parts)
