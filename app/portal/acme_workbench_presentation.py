"""Pure presentation of validated offline context; no runtime authority."""
from html import escape


def render_story_context(cockpit):
    """Never promote an offline payload or accept a receipt as proof."""
    twin = cockpit.get("twin_consumer")
    signal = cockpit.get("signal_context")
    if not isinstance(twin, dict) or not isinstance(signal, dict):
        return "<p>Contexte Twin/Signal : MISSING</p>"
    identity = twin.get("story_identity")
    binding = twin.get("binding")
    if not isinstance(identity, dict) or not isinstance(binding, dict):
        return "<p>Contexte Twin/Signal : UNKNOWN</p>"
    expected = {"namespace": "ACME-DEMO", "incident_id": cockpit.get("incident_id"),
                "impact_incident_id": cockpit.get("business_impact_incident_id"),
                "source_sha256": cockpit.get("source_sha256")}
    digest = expected["source_sha256"]
    if not isinstance(digest, str) or len(digest) != 64:
        return "<p>Contexte Twin/Signal : UNKNOWN</p>"
    expected["run_id"] = "SIM-ACME-" + digest[:16].upper()
    if (identity != expected or any(signal.get(k) != v for k, v in expected.items())
            or twin.get("schema") != "aiops.acme.twin-consumer.v1"
            or signal.get("schema") != "aiops.acme.signal-context.v1"
            or any(x.get("scope") != "STORY_OFFLINE" or x.get("binding_status") != "UNBOUND"
                   for x in (binding, signal))
            or any(k not in binding or binding[k] is not None for k in ("tenant_id", "core_run_id", "attempt_id", "resource_id", "service_id"))
            or any(signal.get(k) is not None for k in ("tenant_id", "attempt_id"))
            or any(x.get("runtime_attested") is not False or x.get("live_remediation_authorized") is not False for x in (twin, signal))):
        return "<p>Contexte Twin/Signal : UNKNOWN — projection incompatible</p>"
    def item(label, value):
        return "<dt>" + escape(label) + "</dt><dd>" + escape(str(value)) + "</dd>"
    return ("<section class='story-context' aria-label='Contexte de provenance'>"
            "<h3>STORY_OFFLINE — UNBOUND</h3><dl>"
            + item("Incident source", identity["incident_id"])
            + item("Incident impacté", identity["impact_incident_id"])
            + item("Run scénario", identity["run_id"])
            + item("Tenant / Core Run / attempt", "UNKNOWN")
            + item("Twin — chemins structurels", twin.get("structural_impact", {}).get("target_path_count", "UNKNOWN"))
            + item("Signal — événements synthétiques", signal.get("unique_count", "UNKNOWN"))
            + item("SHA-256 fixture (intégrité, pas signature)", digest)
            + item("Fraîcheur runtime", "UNKNOWN")
            + "</dl><p>RUNTIME_SANDBOX : UNKNOWN — aucun reçu authentifié. PROD : NO-GO.</p>"
            "<p>États de preuve : MISSING = absente ; UNKNOWN = non qualifiée ; "
            "FAIL = contrôle négatif attesté ; PASS = contrôle positif attesté par le serveur. "
            "Aucun PASS runtime attribué ici.</p></section>")


def render_runtime_refusals(context=None):
    """Presentation of B's refusal-only result, never a receipt verifier.

    No external payload is attached to the offline cockpit. A future server
    adapter may supply its own validated result; this function grants no rights.
    """
    state = "MISSING" if context is None else "UNKNOWN"
    decision = "UNKNOWN"
    if isinstance(context, dict) and (
        context.get("schema") == "aiops.acme.runtime-context.v1"
        and context.get("scope") == "RUNTIME_SANDBOX"
        and context.get("binding_status") == "UNBOUND"
        and context.get("runtime_attested") is False
        and context.get("live_remediation_authorized") is False
        and context.get("runtime_freshness") == "UNKNOWN"
    ):
        if context.get("qualification") == "BLOCK":
            decision = "BLOCK"
        elif context.get("qualification") == "REJECT":
            decision = "REJECT"
            state = "FAIL"
    return ("<p>Validation contexte B : " + state + " — " + decision
            + " (non attesté runtime).</p>"
            "<p>Terminal C : MISSING — aucun reçu terminal indépendant qualifié.</p>"
            "<p>Qualification runtime : UNKNOWN · LIVE : NO-GO.</p>")

# Selective port #192 (8488e64c), timeline_explain.py. Presentation only.
def safe(x):
    return escape(str(x)[:700]) if isinstance(x, (str, int, float, bool)) and x != "" else "MISSING"

def event_facts(e):
    """Render only bounded, recorded Core event data; never invent AI rationale."""
    e = e if isinstance(e, dict) else {}
    payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
    refs = e.get("evidence_ids") if isinstance(e.get("evidence_ids"), list) else []
    parts = []
    if refs:
        parts.append("<p><strong>Preuves liées :</strong> " +
                     ", ".join(safe(x) for x in refs[:30]) + "</p>")
    if e.get("confidence") is not None:
        parts.append("<p><strong>Confiance enregistrée :</strong> " +
                     safe(e["confidence"]) + " (non calibrée)</p>")
    analysis = payload.get("analysis")
    if isinstance(analysis, dict):
        parts.append("<p><strong>Résultat Analyst :</strong> sévérité " +
                     safe(analysis.get("severity")) + ", confiance " +
                     safe(analysis.get("confidence")) + "</p>")
        hypotheses = analysis.get("hypotheses")
        if isinstance(hypotheses, list):
            for h in hypotheses[:5]:
                if isinstance(h, dict):
                    parts.append("<p><strong>Hypothèse :</strong> " +
                                 safe(h.get("statement")) + " · preuves " +
                                 ", ".join(safe(x) for x in (h["supporting_evidence_ids"][:10] if isinstance(h.get("supporting_evidence_ids"), list) else [])) +
                                 "</p>")
    critique = payload.get("critique")
    if isinstance(critique, dict):
        parts.append("<p><strong>Résultat Critic :</strong> validé=" +
                     safe(critique.get("validated")) + " · recommandation " +
                     safe(critique.get("final_recommendation")) + "</p>")
        issues = critique.get("issues")
        if isinstance(issues, list):
            for issue in issues[:12]:
                if isinstance(issue, dict):
                    parts.append("<p><strong>Objection " + safe(issue.get("code")) +
                                 " :</strong> " + safe(issue.get("description")) + "</p>")
    for field in ("reason", "error", "failure_reason", "message"):
        if isinstance(payload.get(field), (str, int, float)):
            parts.append("<p><strong>" + safe(field) + " :</strong> " +
                         safe(payload[field]) + "</p>")
    return "".join(parts) or "<p>Aucune donnée détaillée enregistrée pour cet événement.</p>"




def evidence_catalog(items):
    """Distinguish stage receipts from actual technical observations, without fabrication."""
    if not isinstance(items,list) or not items:
        return '<p>Aucune preuve détaillée liée à ce run.</p>'
    valid = [e for e in items[:200] if isinstance(e,dict) and isinstance(e.get("evidence_id"), str) and 0 < len(e["evidence_id"]) <= 128 and all(c.isascii() and (c.isalnum() or c in "-_") for c in e["evidence_id"])]
    valid = list({e["evidence_id"]: e for e in valid}.values())
    markers = [e for e in valid if isinstance(e.get("provenance"),dict) and
               e["provenance"].get("record_type") == "stage_marker"]
    observations = [e for e in valid if e not in markers]
    if not valid:
        return "<p>Aucune preuve exploitable — UNKNOWN.</p>"
    parts=['<p><strong>Inventaire :</strong> '+str(len(markers))+
           ' marqueur(s) d’exécution · '+str(len(observations))+
           ' autre(s) enregistrement(s) (nature à vérifier).</p>']
    if markers and not observations:
        parts.append('<p><strong>Attention :</strong> ces enregistrements attestent uniquement le passage '+
                     'des étapes. Ils ne démontrent pas une dégradation SAN ou son lien causal avec Payments.</p>')
    parts.append('<p>Entrées offline non attestées. Les payloads bruts ne sont pas exposés.</p>')
    for e in observations + markers:
        eid=str(e["evidence_id"])
        if len(eid)>128 or not all(c.isalnum() or c in "-_" for c in eid):
            continue
        prov=e.get("provenance") if isinstance(e.get("provenance"),dict) else {}
        marker=prov.get("record_type") == "stage_marker"
        kind="Marqueur d’exécution — non probant pour le diagnostic" if marker else "Enregistrement à qualifier"
        parts.append('<details id="proof-'+eid+'"><summary><strong>'+safe(kind)+'</strong> · '+
                     safe(eid)+' · '+safe(e.get("source"))+' · '+safe(e.get("claim"))+'</summary>'+
                     '<p><strong>observed_at — Observé :</strong> '+safe(e.get("observed_at"))+
                     ' · <strong>known_at — Connu :</strong> '+safe(e.get("known_at"))+'</p>'+
                     '<p><strong>Identifiant externe :</strong> '+safe(e.get("external_id"))+
                     ' · <strong>Confiance déclarée :</strong> '+safe(e.get("confidence"))+'</p>'+
                     '<p><strong>Hash enregistré :</strong> '+safe(e.get("payload_hash"))+'</p>'+
                     '<p>Provenance déclarée : '+safe(prov.get("record_type"))+' · synthetic : '+safe(prov.get("synthetic"))+'</p></details>')
    return "".join(parts)



def render_offline_evidence(events=None, evidence=None):
    """Optional injected presentation inputs, not a B/C projection or transport."""
    return ("<details><summary>Observations et marqueurs — offline, non attestés</summary>"
            "<p>UNKNOWN — aucune qualification runtime. NO-GO LIVE.</p>"
            + evidence_catalog(evidence)
            + "".join(event_facts(e) for e in (events[:60] if isinstance(events, list) else []))
            + "</details>")
