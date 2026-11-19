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
            + "</dl>" + render_twin_evidence_plan(twin) + "<p>RUNTIME_SANDBOX : UNKNOWN — aucun reçu authentifié. PROD : NO-GO.</p>"
            "<p>États de preuve : MISSING = absente ; UNKNOWN = non qualifiée ; "
            "FAIL = contrôle négatif attesté ; PASS = contrôle positif attesté par le serveur. "
            "Aucun PASS runtime attribué ici.</p></section>")



def render_twin_evidence_plan(twin):
    """Display structural observations only; never infer runtime health."""
    plan = twin.get("evidence_collection_plan")
    impact = twin.get("structural_impact")
    missing = "<p>Plan de collecte Twin : MISSING / UNKNOWN</p>"
    if not isinstance(plan, dict) or not isinstance(impact, dict):
        return missing
    rows = plan.get("affected_ci_observations")
    alternatives = plan.get("alternative_dependency_observations")
    if (plan.get("scope") != "STORY_OFFLINE"
            or plan.get("ordering") != "STRUCTURAL_DISTANCE_NOT_SEVERITY"
            or plan.get("execution_authorized") is not False
            or not isinstance(rows, list) or not isinstance(alternatives, list)
            or not all(isinstance(r, dict) and isinstance(r.get("ci_id"), str)
                       and type(r.get("minimum_dependency_hops")) is int
                       and r["minimum_dependency_hops"] >= 0
                       and type(r.get("structural_path_count")) is int
                       and r["structural_path_count"] >= 1
                       and r.get("required_observation") == "DEPENDENCY_HEALTH"
                       and r.get("observation_status") == "MISSING" for r in rows)
            or not all(isinstance(r, dict) and isinstance(r.get("ci_id"), str)
                       and r.get("required_observation") == "REDUNDANCY_HEALTH"
                       and r.get("observation_status") == "MISSING" for r in alternatives)
            or sorted(r["ci_id"] for r in rows) != impact.get("affected_ci_ids")
            or [r["ci_id"] for r in alternatives] != impact.get("alternative_dependency_ids")
            or {r["ci_id"]: r["structural_path_count"] for r in rows} != impact.get("path_count_by_ci")
            or rows != sorted(rows, key=lambda r: (r["minimum_dependency_hops"], r["ci_id"]))):
        return missing
    items = "".join("<li><code>" + escape(r["ci_id"]) + "</code> — "
                    + str(r["minimum_dependency_hops"]) + " saut(s), "
                    + str(r["structural_path_count"]) + " chemin(s) ; DEPENDENCY_HEALTH : MISSING</li>"
                    for r in rows)
    alternate_items = "".join("<li><code>" + escape(r["ci_id"])
                              + "</code> — REDUNDANCY_HEALTH : MISSING</li>" for r in alternatives)
    return ("<section aria-label='Plan de collecte Twin'><h3>Plan de collecte Twin</h3>"
            "<p>STORY_OFFLINE — ordre structurel, pas un classement de sévérité. "
            "Aucune collecte exécutée ni autorisée.</p><ol>" + items + "</ol>"
            "<h4>Dépendances alternatives</h4><ul>" + alternate_items + "</ul></section>")

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
