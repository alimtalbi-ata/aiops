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
