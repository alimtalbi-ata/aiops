"""Escaped, script-free HTML projection for computed offline NOC decisions.

Separate from the existing customer DEMO route; never presents simulated data
as authenticated production telemetry.
"""
from __future__ import annotations

from html import escape


def render_computed_noc_html(projection: object) -> str:
    if (not isinstance(projection, dict)
            or projection.get("schema") != "aiops2.synthetic-noc-decision.v1"
            or projection.get("mode") != "SIMULATION"
            or projection.get("scope") != "OFFLINE_NO_EXTERNAL_IO"
            or projection.get("runtime_attested") is not False
            or projection.get("live_remediation_authorized") is not False
            or not isinstance(projection.get("decisions"), list)):
        raise ValueError("unqualified_noc_projection")

    def safe(value: object) -> str:
        return escape(str(value), quote=True)

    rows = []
    for item in projection["decisions"]:
        if (not isinstance(item, dict)
                or item.get("runtime_attested") is not False
                or item.get("live_remediation_authorized") is not False
                or item.get("policy_disposition") != "DENY_LIVE"
                or item.get("impact_state") not in ("UNKNOWN", "SOURCED_SYNTHETIC_PATH")
                or not isinstance(item.get("impact_paths"), list)
                or not isinstance(item.get("analyst"), dict)
                or not isinstance(item.get("critic"), dict)
                or item["critic"].get("root_cause_confirmed") is not False):
            raise ValueError("unqualified_noc_decision")
        paths = item["impact_paths"]
        if item["impact_state"] == "UNKNOWN" and paths:
            raise ValueError("unknown_impact_with_paths")
        if item["impact_state"] == "SOURCED_SYNTHETIC_PATH" and not paths:
            raise ValueError("missing_sourced_path")
        path_labels = []
        for path in paths:
            if not isinstance(path, dict) or not isinstance(path.get("nodes"), list):
                raise ValueError("invalid_noc_path")
            path_labels.append(" → ".join(safe(node) for node in path["nodes"]))
        path_html = "; ".join(path_labels) if path_labels else "UNKNOWN — preuve de dépendance manquante"
        rows.append(
            "<tr><th scope='row'>" + safe(item.get("incident_id", "")) + "</th>"
            "<td>" + safe(item.get("tenant_id", "")) + "</td>"
            "<td>" + safe(item.get("service_id", "")) + "</td>"
            "<td>" + safe(item.get("priority", "")) + "</td>"
            "<td>" + path_html + "</td>"
            "<td>" + safe(item["critic"].get("disposition", "")) + "</td>"
            "<td>" + safe(item.get("next_noc_action", "")) + "</td>"
            "<td>DENY_LIVE</td></tr>"
        )
    body = "".join(rows) or "<tr><td colspan='8'>Aucun incident synthétique admissible</td></tr>"
    return (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>AIOps — Décisions calculées (SIMULATION)</title>"
        "<style>body{font:1rem system-ui,sans-serif;max-width:90rem;margin:2rem auto;"
        "padding:0 1rem;line-height:1.5}table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #999;padding:.6rem;text-align:left;vertical-align:top}"
        "th{background:#eee}table{display:block;overflow-x:auto}</style>"
        "</head><body><main><h1>Décisions NOC calculées — SIMULATION</h1>"
        "<p>Source : pipeline synthétique hors ligne. Aucun runtime LIVE attesté. "
        "Aucune remédiation autorisée.</p>"
        "<table><caption>Incidents corrélés et analyse d'impact</caption>"
        "<thead><tr><th>Incident</th><th>Tenant</th><th>Service</th>"
        "<th>Priorité</th><th>Impact sourcé</th><th>Critic</th>"
        "<th>Prochaine action</th><th>Policy</th></tr></thead>"
        "<tbody>" + body + "</tbody></table></main></body></html>"
    )
