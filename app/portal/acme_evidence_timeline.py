"""Read-only ACME Evidence timeline and business summary from the local synthetic graph.

No browser, upstream, GLPI or runtime read is performed. Missing evidence stays
MISSING. This projection must never be used to attest a LIVE incident or video.
"""
from __future__ import annotations

import html
import re
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from portal.acme_impact_read_model import HEADERS, build_acme_impact_read_model

router = APIRouter()
CUES = ("detect", "correlate", "enrich", "analyze", "ticket",
        "approve", "simulate", "verify", "close")
SERVICES = ("grafana", "n8n", "n8n", "n8n", "glpi",
            "glpi", "n8n", "grafana", "glpi")
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def build_acme_evidence_timeline(model: dict[str, Any] | None = None) -> dict[str, Any]:
    """Project only explicitly absent evidence; reject unqualified upgrades.

    A future runtime-backed timeline needs a separate authenticated, tenant-scoped
    contract. It must not be introduced by changing a synthetic checkpoint flag.
    """
    if model is None:
        model = build_acme_impact_read_model()
    if not isinstance(model, dict):
        raise ValueError("invalid ACME model")
    digest = model.get("source_sha256")
    if not isinstance(digest, str) or not HEX_SHA256.fullmatch(digest):
        raise ValueError("invalid fixture digest")
    if (model.get("schema") != "aiops.synthetic-impact-read-model.v1"
            or model.get("provenance") != "SIMULATED_TARGET"
            or model.get("evidence_source") != "LOCAL_SYNTHETIC_FIXTURE"
            or model.get("run_id") != "SIM-ACME-" + digest[:16].upper()
            or model.get("simulation_ticket_id") != "SIM-GLPI-" + digest[:12].upper()
            or model.get("incident_id") != "ACME-DEMO-SAN-001"
            or model.get("impact_incident_id") != "ACME-DEMO-PAY-002"
            or model.get("ticket_id") is not None
            or model.get("event_timestamp_utc") is not None
            or model.get("runtime_evidence_present") is not False
            or model.get("runtime_attested") is not False
            or model.get("production_qualified") is not False
            or model.get("live_remediation_authorized") is not False):
        raise ValueError("unqualified runtime or correlation claim")
    path = model.get("impact_path")
    affected = model.get("affected_ci_ids")
    if (not isinstance(path, list) or len(path) < 3
            or path[0] != "SAN-FABRIC-A" or path[-1] != "APP-PAY-01"
            or not isinstance(affected, list) or not affected
            or any(not isinstance(ci, str) or not re.fullmatch(r"[A-Z0-9-]{3,64}", ci)
                   for ci in affected)
            or len(set(affected)) != len(affected)
            or not set(path).issubset(set(affected))):
        raise ValueError("invalid synthetic business dependency graph")
    checkpoints = model.get("checkpoint_evidence")
    if not isinstance(checkpoints, list) or len(checkpoints) != len(CUES):
        raise ValueError("missing checkpoint contract")
    timeline = []
    for index, (cue, service, item) in enumerate(zip(CUES, SERVICES, checkpoints), 1):
        if (not isinstance(item, dict) or item.get("cue") != cue
                or item.get("service") != service
                or not isinstance(item.get("view"), str) or not item["view"]
                or not isinstance(item.get("required_state"), str)
                or not item["required_state"]
                or item.get("status") != "MISSING"
                or item.get("screenshot_sha256") is not None
                or item.get("event_timestamp_utc") is not None
                or item.get("runtime_authenticated") is not False
                or item.get("source") != "CHECKPOINT_CONTRACT_ONLY_NO_CAPTURE"):
            raise ValueError("checkpoint is not verified missing synthetic evidence")
        timeline.append({
            "sequence": index, "cue": cue, "service": service,
            "expected_view": item["view"], "expected_state": item["required_state"],
            "evidence_status": "MISSING", "capture_sha256": None,
            "observed_at_utc": None, "runtime_authenticated": False,
        })
    return {
        "schema": "aiops.acme-evidence-timeline.v1",
        "provenance": "SIMULATED_TARGET",
        "source_sha256": digest,
        "run_id": model["run_id"],
        "incident_id": model["incident_id"],
        "impact_incident_id": model["impact_incident_id"],
        "glpi_ticket_id": None,
        "simulation_ticket_id": model["simulation_ticket_id"],
        "timeline": timeline,
        "business_summary": {
            "service": "ACME Payments",
            "source_severity": "P1_SYNTHETIC",
            "downstream_severity": "P2_SYNTHETIC",
            "dependency_path": list(path),
            "potentially_affected_ci_count_from_fixture": len(affected),
            "observed_service_availability": "UNKNOWN",
            "observed_downtime_minutes": None,
            "observed_affected_transactions": None,
            "observed_financial_loss_eur": None,
            "recovery_verified": False,
        },
        "capture_status": "BLOCKED_NO_AUTHENTICATED_CAPTURES",
        "video_ready": False,
        "runtime_authenticated": False,
        "production_qualified": False,
        "live_remediation_authorized": False,
    }


def _load_or_503():
    try:
        return build_acme_evidence_timeline()
    except (ValueError, OSError, UnicodeError, ImportError, AttributeError) as exc:
        raise HTTPException(status_code=503, detail="synthetic_evidence_timeline_unavailable") from exc


@router.get("/api/demo/acme-evidence-timeline")
def acme_evidence_timeline_json():
    return JSONResponse(content=_load_or_503(), headers=HEADERS)


@router.get("/demo/acme-evidence-timeline", response_class=HTMLResponse)
def acme_evidence_timeline_page():
    model = _load_or_503()
    rows = "".join(
        "<tr><td>" + str(item["sequence"]) + "</td><td>"
        + html.escape(item["cue"]) + "</td><td>"
        + html.escape(item["service"]) + "</td><td>"
        + html.escape(item["expected_view"]) + "</td><td>MISSING — aucune capture authentifiée</td></tr>"
        for item in model["timeline"]
    )
    summary = model["business_summary"]
    path = " → ".join(html.escape(x) for x in summary["dependency_path"])
    body = (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>ACME — Timeline Evidence (SIMULATION)</title>'
        '<style>body{background:#0b1220;color:#eef5ff;font:16px/1.5 system-ui;margin:0}'
        'main{max-width:1100px;margin:auto;padding:24px}a{color:#8fd0ff}'
        'table{border-collapse:collapse;width:100%}th,td{border:1px solid #40516a;padding:10px;text-align:left}'
        'th{background:#1a3048}.warning{border:2px solid #ffc66d;padding:14px}'
        'code{overflow-wrap:anywhere}@media(max-width:700px){table{font-size:12px}th,td{padding:5px}}</style>'
        '</head><body><main><p><a href="/demo/acme-impact">Impact ACME</a></p>'
        '<h1>Timeline Evidence — ACME (SIMULATION LOCALE UNIQUEMENT)</h1>'
        '<p class="warning">Aucune preuve runtime, aucune session Playwright authentifiée, '
        'aucun ticket GLPI réel. Vidéo client BLOQUÉE.</p>'
        '<p>Run fictif : <code>' + html.escape(model["run_id"]) + '</code> · '
        'Incident SAN : <code>' + html.escape(model["incident_id"]) + '</code> · '
        'Impact Payments : <code>' + html.escape(model["impact_incident_id"]) + '</code></p>'
        '<h2>Étapes attendues, non observées</h2><table><thead><tr>'
        '<th>#</th><th>Étape</th><th>Service</th><th>Vue attendue</th><th>Preuve</th>'
        '</tr></thead><tbody>' + rows + '</tbody></table>'
        '<h2>Bilan métier — hypothèse du graphe local</h2>'
        '<p>Chemin potentiel : ' + path + '</p>'
        '<p>CI potentiellement touchés dans le fixture : '
        + str(summary["potentially_affected_ci_count_from_fixture"]) + '</p>'
        '<p>Disponibilité observée : UNKNOWN · Transactions affectées : UNKNOWN · '
        'Durée d’interruption : UNKNOWN · Perte financière : UNKNOWN · '
        'Rétablissement vérifié : NON.</p>'
        '<p>Les nombres de ce graphe ne sont ni des mesures de production ni une estimation financière.</p>'
        '</main></body></html>'
    )
    return HTMLResponse(body, headers=HEADERS)
