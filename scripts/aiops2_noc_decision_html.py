"""Escaped, script-free HTML projection for computed offline NOC decisions.

Separate from the existing customer DEMO route; never presents simulated data
as authenticated production telemetry.
"""
from __future__ import annotations

from html import escape
import re

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


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

    if len(projection["decisions"]) > 100:
        raise ValueError("noc_projection_decision_budget_exceeded")
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
                or item["critic"].get("root_cause_confirmed") is not False
                or item["critic"].get("citations_valid") is not True
                or item["analyst"].get("kind") != "HYPOTHESIS_NOT_ROOT_CAUSE"
                or item["critic"].get("runtime_attested") is not False
                or item["critic"].get("disposition") not in (
                    "SUPPORTED_SYNTHETIC_HYPOTHESIS", "NEEDS_MORE_EVIDENCE")
                or item["analyst"].get("impact_state") != item["impact_state"]):
            raise ValueError("unqualified_noc_decision")
        # Bound all incident metadata rendered into the HTML table.
        if not all(isinstance(item.get(field), str) and 0 < len(item[field]) <= 256
                   for field in ("incident_id", "tenant_id", "service_id", "priority")):
            raise ValueError("invalid_noc_display_metadata")
        origins = item.get("incident_ci_ids")
        if (not isinstance(origins, list) or not origins or len(origins) > 100
                or not all(isinstance(ci, str) and 0 < len(ci) <= 256 for ci in origins)
                or len(set(origins)) != len(origins)):
            raise ValueError("invalid_noc_incident_origins")
        paths = item["impact_paths"]
        if len(paths) > 100:
            raise ValueError("noc_projection_path_budget_exceeded")
        if item["impact_state"] == "UNKNOWN" and paths:
            raise ValueError("unknown_impact_with_paths")
        if item["impact_state"] == "SOURCED_SYNTHETIC_PATH" and not paths:
            raise ValueError("missing_sourced_path")
        if ((item["impact_state"] == "UNKNOWN"
                and item["critic"]["disposition"] != "NEEDS_MORE_EVIDENCE")
                or (item["impact_state"] == "SOURCED_SYNTHETIC_PATH"
                    and item["critic"]["disposition"] != "SUPPORTED_SYNTHETIC_HYPOTHESIS")):
            raise ValueError("contradictory_noc_critic")
        expected_missing = ([] if item["impact_state"] == "SOURCED_SYNTHETIC_PATH"
                            else ["SOURCED_DEPENDENCY_PATH"])
        if item["analyst"].get("missing_evidence") != expected_missing:
            raise ValueError("contradictory_noc_missing_evidence")
        expected_action = ("REVIEW_SYNTHETIC_EVIDENCE"
                           if item["impact_state"] == "SOURCED_SYNTHETIC_PATH"
                           else "COLLECT_MISSING_DEPENDENCY_EVIDENCE")
        if item.get("next_noc_action") != expected_action:
            raise ValueError("contradictory_noc_next_action")
        citations = item["analyst"].get("evidence_sha256")
        if (not isinstance(citations, list) or not citations
                or len(citations) > 10000
                or not all(isinstance(digest, str) and _DIGEST.fullmatch(digest)
                           for digest in citations)
                or citations != sorted(set(citations))):
            raise ValueError("invalid_noc_analyst_citations")
        citation_set = set(citations)
        path_labels = []
        for path in paths:
            if (not isinstance(path, dict) or not isinstance(path.get("nodes"), list)
                    or len(path["nodes"]) > 100
                    or len(path["nodes"]) < 2
                    or not all(isinstance(node, str) and node and len(node) <= 256
                               for node in path["nodes"])
                    or len(set(path["nodes"])) != len(path["nodes"])
                    or path["nodes"][0] not in origins
                    or path["nodes"][-1] != item.get("service_id")
                    or not isinstance(path.get("evidence_sha256"), list)
                    or len(path["evidence_sha256"]) != len(path["nodes"]) - 1
                    or not all(isinstance(digest, str) and _DIGEST.fullmatch(digest)
                               for digest in path["evidence_sha256"])):
                raise ValueError("invalid_noc_path")
            if not set(path["evidence_sha256"]).issubset(citation_set):
                raise ValueError("uncited_noc_dependency_path")
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
