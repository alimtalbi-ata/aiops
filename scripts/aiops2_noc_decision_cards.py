"""Accessible read-only decision cards for qualified offline NOC projections.

This is a candidate renderer, deliberately not wired into LIVE or existing routes.
"""
from html import escape


def render_decision_cards(projection: dict) -> str:
    if (not isinstance(projection, dict)
        or projection.get("schema") != "aiops2.synthetic-noc-decision.v1"
        or projection.get("mode") != "SIMULATION"
        or projection.get("scope") != "OFFLINE_NO_EXTERNAL_IO"
        or projection.get("runtime_attested") is not False
        or projection.get("live_remediation_authorized") is not False
        or not isinstance(projection.get("decisions"), list)):
        raise ValueError("unqualified_projection")

    def e(value):
        return escape(str(value), quote=True)

    cards = []
    for decision in projection["decisions"]:
        if (not isinstance(decision, dict)
            or decision.get("policy_disposition") != "DENY_LIVE"
            or decision.get("runtime_attested") is not False
            or decision.get("live_remediation_authorized") is not False
            or decision.get("impact_state") not in ("UNKNOWN", "SOURCED_SYNTHETIC_PATH")
            or not isinstance(decision.get("impact_paths"), list)
            or not isinstance(decision.get("analyst"), dict)
            or not isinstance(decision.get("critic"), dict)
            or decision["critic"].get("root_cause_confirmed") is not False):
            raise ValueError("unqualified_decision")
        paths = decision["impact_paths"]
        if (decision["impact_state"] == "UNKNOWN" and paths) or (
            decision["impact_state"] == "SOURCED_SYNTHETIC_PATH" and not paths
        ):
            raise ValueError("inconsistent_impact")
        count = decision.get("event_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError("invalid_correlated_alert_count")
        if not isinstance(decision.get("incident_id"), str) or not decision["incident_id"].strip():
            raise ValueError("missing_incident_id")
        analyst = decision["analyst"]
        critic = decision["critic"]
        if (not isinstance(analyst.get("hypothesis"), str)
            or not analyst["hypothesis"].strip()
            or not isinstance(critic.get("disposition"), str)
            or not critic["disposition"].strip()):
            raise ValueError("missing_analyst_critic_assessment")
        labels = []
        for path in paths:
            if not isinstance(path, dict) or not isinstance(path.get("nodes"), list):
                raise ValueError("invalid_path")
            nodes = path["nodes"]
            if len(nodes) < 2 or any(not isinstance(n, str) or not n.strip() for n in nodes):
                raise ValueError("invalid_path_nodes")
            labels.append(" → ".join(e(n) for n in nodes))
        impact = ("UNKNOWN — provenance non attestée ; chemin proposé (simulation) : " + "; ".join(labels)) if labels else "UNKNOWN — dépendance non prouvée"
        cards.append(
            "<article aria-label='Incident " + e(decision.get("incident_id", "UNKNOWN")) + "'>"
            "<h2>" + e(decision.get("incident_id", "UNKNOWN")) + "</h2>"
            "<dl><dt>Priorité</dt><dd>" + e(decision.get("priority", "UNKNOWN")) + "</dd>"
            "<dt>Service</dt><dd>" + e(decision.get("service_id", "UNKNOWN")) + "</dd>"
            "<dt>Alertes corrélées</dt><dd>" + e(decision.get("event_count", "UNKNOWN")) + "</dd>"
            "<dt>Impact SAN → Payments (simulation)</dt><dd>" + impact + "</dd>"
            "<dt>Hypothèse Analyst</dt><dd>" + e(analyst["hypothesis"]) + "</dd>"
            "<dt>Réserve Critic</dt><dd>" + e(critic["disposition"]) + " — cause racine non confirmée</dd>"
            "<dt>Incertitude</dt><dd>Cause racine non confirmée ; chemin non attesté (source, fraîcheur et version du graphe UNKNOWN) ; données synthétiques uniquement</dd>"
            "<dt>Prochaine action NOC</dt><dd>" + e(decision.get("next_noc_action", "UNKNOWN")) + "</dd>"
            "<dt>Décision Policy</dt><dd>DENY_LIVE</dd></dl></article>"
        )
    body = "".join(cards) or "<p>Aucun incident synthétique calculé.</p>"
    return (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Cockpit NOC — SIMULATION</title><style>"
        "body{font:1rem/1.6 system-ui,sans-serif;margin:0 auto;padding:1rem;max-width:80rem;"
        "color:#172033;background:#fff}main{min-width:0}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,20rem),1fr));gap:1rem}"
        "article{border:2px solid #44546a;border-radius:.7rem;padding:1rem;min-width:0;"
        "overflow-wrap:anywhere}dt{font-weight:700;margin-top:.6rem}dd{margin:0}"
        ":focus-visible{outline:3px solid #004ecc;outline-offset:3px}"
        "@media(max-width:400px){body{padding:.6rem}article{padding:.7rem}}"
        "</style></head><body><main><h1>Cockpit décisionnel — SIMULATION</h1>"
        "<p role='status'>Données calculées hors ligne. LIVE non attesté. "
        "Policy DENY_LIVE ; aucune action exécutable.</p>"
        "<section class='grid' aria-label='Incidents calculés'>" + body
        + "</section></main></body></html>"
    )
