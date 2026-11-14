"""Script-free operator presentation for the unified synthetic incident cockpit."""
from __future__ import annotations

from html import escape


def render_synthetic_cockpit_html(cockpit: dict) -> str:
    if (not isinstance(cockpit, dict)
            or cockpit.get("schema") != "aiops.synthetic-incident-cockpit.v1"
            or cockpit.get("mode") != "DEMO"
            or cockpit.get("overall_qualification") != "UNKNOWN"
            or cockpit.get("runtime_attested") is not False
            or cockpit.get("live_remediation_authorized") is not False):
        raise ValueError("unqualified_cockpit_html")
    lifecycle = cockpit["lifecycle"]
    readiness = cockpit["itil_readiness"]
    evidence = cockpit["evidence_plan"]
    review = cockpit["analyst_critic_review"]
    if (len(lifecycle["stages"]) != 9 or len(readiness["transitions"]) != 8
            or evidence["requested_count"] != 9 or evidence["verified_count"] != 0
            or review["policy_disposition"] != "DENY_LIVE_ACTION"
            or review["critic_disposition"] != "HOLD_FOR_HUMAN_REVIEW"
            or any(stage["evidence_state"] != "UNKNOWN" for stage in lifecycle["stages"])
            or any(t["authorized"] is not False for t in readiness["transitions"])
            or any(r["evidence_state"] != "MISSING" for r in evidence["requests"])):
        raise ValueError("unqualified_cockpit_details")
    def safe(value: object) -> str:
        return escape(str(value), quote=True)
    stage_rows = "".join(
        "<tr><th scope='row'>" + safe(s["phase"]) + "</th><td>"
        + safe(s["expected_source"]) + "</td><td>" + safe(s["evidence_state"])
        + "</td></tr>" for s in lifecycle["stages"]
    )
    transition_rows = "".join(
        "<tr><th scope='row'>" + safe(t["transition"]) + "</th><td>"
        + safe(", ".join(t["missing_evidence"])) + "</td><td>NON</td></tr>"
        for t in readiness["transitions"]
    )
    return (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>AIOPS2 — Cockpit incident DEMO</title>"
        "<style>body{font:16px system-ui,sans-serif;max-width:1150px;margin:2rem auto;"
        "padding:0 1rem;line-height:1.5}table{border-collapse:collapse;width:100%;"
        "margin:1rem 0 2rem}th,td{border:1px solid #777;padding:.6rem;text-align:left}"
        "thead{background:#eee;color:#111}.warning{border-left:5px solid #9a6700;"
        "padding:1rem;background:#fff7dd;color:#302400}"
        "code{overflow-wrap:anywhere}</style></head><body><main>"
        "<h1>AIOPS2 — Cockpit incident → ITIL</h1>"
        "<p class='warning'><strong>DEMO SYNTHÉTIQUE — NO-GO LIVE.</strong> "
        "Aucune preuve runtime authentifiée, aucun ticket GLPI modifié, "
        "aucune exécution Temporal ni remédiation autorisée.</p>"
        "<h2>Parcours démontrable — SAN vers Payments</h2>"
        "<p>Signal SAN → incident P1 → impact Payments → hypothèses Analyst/Critic "
        "→ décision Policy/HITL → simulation isolée → vérification indépendante "
        "→ préparation ITIL.</p>"
        "<p><strong>Ce qui est démontré :</strong> corrélation des identifiants "
        "et empreinte de la même fixture synthétique; neuf étapes et huit "
        "transitions inspectables. <strong>Ce qui reste inconnu :</strong> "
        "preuve runtime, effet réel, récupération indépendante et autorisation "
        "de clôture.</p>"
        "<p>Contrat de démonstrabilité : <code>"
        "python scripts/verify_aiops2_demo_acceptance.py</code> "
        "(rapport JSON hors ligne; pas une attestation de production).</p>"
        "<p><a href='/demo/acme-grafana-pilot-preview'>Voir l'observation Grafana synthétique non attestée</a> — "
        "UNKNOWN / BLOCKED, sans accès réseau ni qualification runtime.</p>"
        "<h2>Incident et impact métier</h2><p>SAN P1 : <code>"
        + safe(cockpit["incident_id"]) + "</code> · Payments P2 : <code>"
        + safe(cockpit["business_impact_incident_id"]) + "</code></p>"
        "<p>Chemin d'impact : " + safe(" → ".join(cockpit["business_impact_path"]))
        + "</p><h2>Cycle incident (9 étapes)</h2><table><thead><tr>"
        "<th>Étape</th><th>Source attendue</th><th>Preuve</th></tr></thead>"
        "<tbody>" + stage_rows + "</tbody></table>"
        "<h2>Transitions ITIL (8)</h2><table><thead><tr>"
        "<th>Transition</th><th>Preuves manquantes</th><th>Autorisée</th>"
        "</tr></thead><tbody>" + transition_rows + "</tbody></table>"
        "<h2>Analyst / Critic / Policy</h2><p>Analyst : hypothèse déterministe, "
        "pas une conclusion LLM vérifiée. Critic : "
        + safe(review["critic_disposition"]) + ". Policy : "
        + safe(review["policy_disposition"]) + ".</p>"
        "<p>Preuves indépendantes vérifiées : <strong>0 / "
        + safe(evidence["requested_count"]) + "</strong>. "
        "Prochaine action : collecte manuelle en lecture seule, "
        "puis vérification indépendante.</p>"
        "<p>SHA-256 de la fixture : <code>" + safe(cockpit["source_sha256"])
        + "</code></p></main></body></html>"
    )
