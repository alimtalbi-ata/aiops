"""Script-free read-only Grafana pilot preview; no network and no runtime claims."""
from html import escape


def render_grafana_pilot_preview_html(preview):
    if (not isinstance(preview, dict)
            or preview.get("schema") != "aiops2.grafana-pilot-preview.v1"
            or preview.get("qualification") != "UNKNOWN"
            or preview.get("reason") != "INJECTED_TRANSPORT_NOT_AUTHENTICATED"
            or preview.get("runtime_attested") is not False
            or preview.get("live_actions_authorized") is not False):
        raise ValueError("grafana_pilot_preview_unqualified")
    register = preview.get("register")
    if (not isinstance(register, dict)
            or register.get("schema") != "aiops2.readonly-pilot-evidence-register.v1"
            or register.get("decision") != "BLOCKED"
            or register.get("live_actions_authorized") is not False):
        raise ValueError("grafana_pilot_register_unqualified")
    sources = register.get("sources")
    if not isinstance(sources, dict) or not isinstance(sources.get("grafana"), dict):
        raise ValueError("grafana_pilot_source_missing")
    grafana = sources["grafana"]
    if grafana.get("status") != "UNKNOWN" or grafana.get("evidence_refs") != []:
        raise ValueError("grafana_pilot_evidence_not_attested")
    if grafana.get("alert_state") not in ("firing", "pending", "normal"):
        raise ValueError("grafana_pilot_alert_state_invalid")
    fields = (("Règle SAN", "rule_uid"), ("État candidat", "alert_state"), ("Dashboard", "dashboard_uid"),
              ("Tenant de test déclaré", "tenant_scope"),
              ("Observation déclarée", "observed_at_utc"),
              ("Identité de collecte déclarée", "service_identity"),
              ("Empreinte locale", "response_sha256"))
    rows = []
    for label, key in fields:
        value = grafana.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError("grafana_pilot_field_missing")
        rows.append("<tr><th scope='row'>" + escape(label) + "</th><td><code>"
                    + escape(value, quote=True) + "</code></td></tr>")
    scenario = preview.get("synthetic_scenario")
    scenario_html = ""
    if scenario is not None:
        if (not isinstance(scenario, dict)
                or scenario.get("qualification") != "UNKNOWN"
                or any(not isinstance(scenario.get(k), str) or not scenario[k]
                       for k in ("incident_id", "business_impact_incident_id", "source_sha256"))
                or len(scenario["source_sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in scenario["source_sha256"])):
            raise ValueError("grafana_pilot_scenario_unqualified")
        scenario_html = (
            "<h2>Corrélation avec le cockpit synthétique</h2>"
            "<p>Incident SAN P1 : <code>" + escape(scenario["incident_id"], quote=True)
            + "</code> · Impact Payments P2 : <code>"
            + escape(scenario["business_impact_incident_id"], quote=True)
            + "</code></p><p>SHA-256 de la fixture du cockpit : <code>"
            + escape(scenario["source_sha256"], quote=True) + "</code></p>"
            "<p>Ces identifiants relient deux vues de la même simulation; "
            "ils ne prouvent aucune corrélation runtime.</p>"
        )
    return (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>AIOPS2 — SAN vers Payments — aperçu Grafana</title>"
        "<style>body{font:16px system-ui,sans-serif;max-width:900px;margin:2rem auto;"
        "padding:0 1rem;line-height:1.5}table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #777;padding:.6rem;text-align:left}"
        "code{overflow-wrap:anywhere}.warning{border-left:5px solid #a60;"
        "padding:1rem;background:#fff3cf}</style></head><body><main>"
        "<h1>AIOPS2 — SAN → Payments : observation Grafana</h1>"
        "<p class='warning'><strong>APERÇU NON ATTESTÉ — UNKNOWN / BLOCKED.</strong> "
        "Source injectée et non authentifiée; aucune ACL native Grafana vérifiée, "
        "aucune preuve de récupération, aucun ticket GLPI écrit et aucune action LIVE.</p>"
        "<p><a href='/demo/acme-incident-cockpit'>Retour au cockpit incident SAN → Payments</a></p>"
        "<h2>Observation candidate — lecture seule</h2><table><tbody>"
        + "".join(rows) + "</tbody></table>"
        + scenario_html + "<h2>Chaîne métier attendue</h2>"
        "<p>Signal SAN → incident P1 → dépendance Payments → preuve authentifiée "
        "→ Analyst/Critic → Policy/HITL → simulation → postcheck indépendant → ITIL.</p>"
        "<p><strong>Prochaine porte :</strong> vérifier l'identité de transport, "
        "l'isolation tenant, la provenance indépendante et les tests négatifs "
        "avant de qualifier une observation runtime.</p>"
        "<p><strong>Décision :</strong> BLOCKED · <strong>LIVE :</strong> NO-GO.</p>"
        "</main></body></html>"
    )
