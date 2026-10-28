"""Read-only ACME Golden DEMO Run readback through the canonical portal.

An authenticated Core GET confirms only identity and state at read time.
Neither a Core status nor a local fixture proves Temporal execution, GLPI
correlation, service recovery, screenshot authenticity or LIVE authority.
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Header, HTTPException

from portal import noc_correlation, noc_runtime
from portal.acme_golden_demo import RUN_ID, SCENARIO_ID
from portal.acme_impact_read_model import build_acme_impact_read_model
from shared.domain import STATUSES

router = APIRouter()
SCHEMA = "aiops.acme-golden-run-readback.v1"
SHA256 = re.compile(r"[0-9a-f]{64}\\Z")


def _unverified(reason: str) -> dict[str, Any]:
    """Never expose an unrelated tenant's canonical identifiers on mismatch."""
    return {
        "schema": SCHEMA,
        "state": "UNKNOWN",
        "reason": reason,
        "canonical_run_id": None,
        "canonical_incident_id": None,
        "mode": None,
        "run_status": None,
        "run_version": None,
        "glpi_ticket_id": None,
        "glpi_correlation": "UNKNOWN",
        "runtime_attested": False,
        "production_qualified": False,
        "live_remediation_authorized": False,
    }


def project_acme_run(requested_run_id: str, run: dict, fixture: dict) -> dict[str, Any]:
    """Join only the exact DEMO Run/Incident/scenario with the validated fixture."""
    if (
        not isinstance(fixture, dict)
        or fixture.get("provenance") != "SIMULATED_TARGET"
        or fixture.get("incident_id") != "ACME-DEMO-SAN-001"
        or fixture.get("impact_incident_id") != "ACME-DEMO-PAY-002"
        or fixture.get("ticket_id") is not None
        or fixture.get("runtime_attested") is not False
        or fixture.get("live_remediation_authorized") is not False
        or not isinstance(fixture.get("source_sha256"), str)
        or SHA256.fullmatch(fixture["source_sha256"]) is None
    ):
        raise ValueError("untrusted ACME fixture")
    if not isinstance(requested_run_id, str) or RUN_ID.fullmatch(requested_run_id) is None:
        raise ValueError("invalid Run ID")
    if not isinstance(run, dict):
        return _unverified("CORE_RUN_UNVERIFIED")

    expected_incident = "INC-" + fixture["incident_id"]
    if (
        run.get("run_id") != requested_run_id
        or run.get("incident_id") != expected_incident
        or run.get("scenario_id") != SCENARIO_ID
        or run.get("mode") != "DEMO"
        or type(run.get("version")) is not int
        or run["version"] < 1
        or run.get("status") not in STATUSES
    ):
        return _unverified("CORE_IDENTITY_MODE_OR_STATE_MISMATCH")

    return {
        "schema": SCHEMA,
        "state": "MATCHED_UNATTESTED",
        "reason": "CORE_DEMO_IDENTITY_READBACK_ONLY",
        "canonical_run_id": requested_run_id,
        "canonical_incident_id": expected_incident,
        "fixture_incident_id": fixture["incident_id"],
        "fixture_impact_incident_id": fixture["impact_incident_id"],
        "fixture_sha256": fixture["source_sha256"],
        "scenario_id": SCENARIO_ID,
        "mode": "DEMO",
        "run_status": run["status"],
        "run_version": run["version"],
        "glpi_ticket_id": None,
        "glpi_correlation": "UNKNOWN",
        "execution_evidence": "NOT_TESTED",
        "source": "CANONICAL_CORE_GET_NOT_RUNTIME_ATTESTATION",
        "runtime_attested": False,
        "production_qualified": False,
        "live_remediation_authorized": False,
    }


@router.get("/api/demo/acme-run/{run_id}", name="authenticated_acme_run_readback")
def acme_run_readback(run_id: str, authorization: str | None = Header(default=None)):
    """Require operator auth before any fixture or Core read; fail closed."""
    try:
        noc_runtime._require_portal_read_auth(authorization)
    except HTTPException as exc:
        return noc_runtime._noc_json_response({"detail": exc.detail}, status_code=exc.status_code)
    if RUN_ID.fullmatch(run_id) is None:
        return noc_runtime._noc_json_response(
            {"detail": "invalid_demo_run_identifier"}, status_code=400
        )
    try:
        fixture = build_acme_impact_read_model()
        run = noc_correlation._read_core_run(run_id)
        result = project_acme_run(run_id, run, fixture)
    except Exception:
        return noc_runtime._noc_json_response(
            {"detail": "acme_run_readback_unavailable_or_unverified"}, status_code=503
        )
    return noc_runtime._noc_json_response(result)
