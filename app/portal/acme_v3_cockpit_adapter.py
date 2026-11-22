"""V3 selective adapter: read-only ACME cockpit from one validated local fixture.

No Core/Temporal/Worker/GLPI calls, no tenant binding and no runtime claims.
Existing /api/demo/acme-impact and /demo/acme-impact routes remain unchanged.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from portal.acme_impact_read_model import (
    FIXTURE_PATH, HEADERS, _read_fixture_bytes_safely, build_acme_impact_read_model,
)
from portal.acme_twin_provenance import build_twin_evidence
from portal.acme_twin_consumer import project_twin_consumer
from portal.acme_signal_context import build_signal_context
from portal.acme_incident_cockpit import project_synthetic_incident_cockpit
from portal.acme_incident_cockpit_html import render_synthetic_cockpit_html

router = APIRouter()


def build_v3_synthetic_cockpit() -> dict:
    """Fail closed if impact and Twin evidence do not share exact fixture bytes."""
    raw = _read_fixture_bytes_safely(FIXTURE_PATH)
    impact = build_acme_impact_read_model()
    twin = build_twin_evidence(raw)
    if (impact.get("source_sha256") != twin.get("source_sha256")
            or impact.get("run_id") != twin.get("run_id")
            or impact.get("incident_id") != twin.get("incident_id")
            or impact.get("impact_incident_id") != twin.get("impact_incident_id")
            or impact.get("impact_path") != twin.get("impact", {}).get("impact_path")
            or impact.get("affected_ci_ids") != twin.get("impact", {}).get("affected_ci_ids")
            or impact.get("runtime_attested") is not False
            or impact.get("live_remediation_authorized") is not False):
        raise ValueError("v3_fixture_snapshot_or_identity_mismatch")
    impact["twin_evidence"] = twin
    impact["twin_consumer"] = project_twin_consumer(impact)
    impact["signal_context"] = build_signal_context(twin)
    cockpit = project_synthetic_incident_cockpit(impact)
    journey = cockpit.get("run_journey")
    if (cockpit.get("overall_qualification") != "UNKNOWN"
            or cockpit.get("runtime_attested") is not False
            or cockpit.get("live_remediation_authorized") is not False
            or not isinstance(journey, dict)
            or journey.get("scope") != "STORY_OFFLINE"
            or journey.get("receipt") is not None
            or journey.get("policy", {}).get("decision") != "DENY_LIVE_ACTION"):
        raise ValueError("v3_cockpit_authority_mismatch")
    return cockpit


def _load_or_503() -> dict:
    try:
        return build_v3_synthetic_cockpit()
    except (OSError, UnicodeError, ValueError, ImportError, AttributeError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="v3_synthetic_cockpit_unavailable_or_invalid") from exc


@router.get("/api/demo/v3/acme-incident-cockpit", name="v3_synthetic_acme_cockpit_json")
def v3_synthetic_acme_cockpit_json():
    return JSONResponse(_load_or_503(), headers=HEADERS)


@router.get("/demo/v3/acme-incident-cockpit", response_class=HTMLResponse, name="v3_synthetic_acme_cockpit_html")
def v3_synthetic_acme_cockpit_html():
    return HTMLResponse(render_synthetic_cockpit_html(_load_or_503()), headers=HEADERS)
