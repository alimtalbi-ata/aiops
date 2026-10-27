"""Read-only, fail-closed correlation of synthetic ACME IDs with signed NOC and Core.

The NOC source signs a claim, not a GLPI ticket or an authenticated runtime capture.
Core GET returns a canonical Run record but does not attest the NOC or GLPI source.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from portal.acme_impact_read_model import HEADERS, build_acme_impact_read_model
from portal.noc_runtime import (
    IDENTIFIER, _require_portal_read_auth, read_signed_noc_snapshot,
)

router = APIRouter()
SCHEMA = "aiops.acme.itsm-correlation.v1"


def project_correlation(scenario: dict, noc: object = None, core: object = None) -> dict:
    """Never promote upstream claims into verified GLPI tickets or LIVE permission."""
    result = {
        "schema": SCHEMA,
        "state": "UNKNOWN",
        "reason": "MISSING_OR_UNVERIFIED_CORRELATION",
        "scenario_provenance": "SIMULATED_TARGET",
        "scenario_incident_id": scenario["incident_id"],
        "scenario_run_label": scenario["run_id"],
        "core_run_id": None,
        "core_incident_id": None,
        "core_read_provenance": "UNATTESTED_CORE_API_READ",
        "noc_payload_authenticated": False,
        "noc_payload_sha256": None,
        "glpi_ticket_claim": None,
        "ticket_id": None,
        "ticket_verification": "NOT_TESTED_NO_GLPI_API_READ",
        "runtime_attested": False,
        "production_qualified": False,
        "live_remediation_authorized": False,
    }
    if (
        not isinstance(noc, dict)
        or noc.get("source_payload_authenticated") is not True
        or noc.get("source_authentication") != "HMAC_SHA256_VERIFIED"
        or noc.get("runtime_attested") is not False
        or noc.get("production_qualified") is not False
        or noc.get("live_remediation_authorized") is not False
    ):
        return result
    digest = noc.get("source_payload_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        return result
    result["noc_payload_authenticated"] = True
    result["noc_payload_sha256"] = digest
    run_id = noc.get("run_id")
    incident_id = noc.get("incident_id")
    expected_incident = "INC-" + scenario["incident_id"]
    if (
        not isinstance(run_id, str)
        or IDENTIFIER.fullmatch(run_id) is None
        or incident_id != expected_incident
        or not isinstance(core, dict)
        or not isinstance(core.get("run"), dict)
    ):
        return result
    run = core["run"]
    if (
        run.get("run_id") != run_id
        or run.get("incident_id") != expected_incident
        or run.get("mode") != "DEMO"
        or type(run.get("version")) is not int
        or run["version"] < 1
        or not isinstance(run.get("scenario_id"), str)
        or IDENTIFIER.fullmatch(run["scenario_id"]) is None
    ):
        return result
    result["state"] = "CORRELATED_UNVERIFIED"
    result["reason"] = "CORE_RUN_MATCHES_SIGNED_NOC_CLAIM_NO_GLPI_ATTESTATION"
    result["core_run_id"] = run_id
    result["core_incident_id"] = expected_incident
    ticket_claim = noc.get("ticket_id")
    if isinstance(ticket_claim, str) and ticket_claim and not ticket_claim.startswith("SIM-"):
        # Signed NOC assertion only; GLPI itself has NOT been queried.
        result["glpi_ticket_claim"] = ticket_claim
    return result


@router.get("/api/portal/acme-correlation", name="acme_signed_noc_core_correlation")
def acme_correlation(authorization: str | None = Header(default=None)):
    """Authenticated portal read. No writes, no GLPI request and no LIVE actions."""
    _require_portal_read_auth(authorization)
    try:
        scenario = build_acme_impact_read_model()
    except (OSError, ValueError, ImportError, AttributeError):
        return JSONResponse(
            {"schema": SCHEMA, "state": "UNKNOWN", "reason": "SCENARIO_UNAVAILABLE",
             "ticket_id": None, "live_remediation_authorized": False},
            status_code=503, headers=HEADERS,
        )
    try:
        noc = read_signed_noc_snapshot()
    except (OSError, ValueError, KeyError, TypeError):
        noc = None
    core = None
    if isinstance(noc, dict) and noc.get("source_payload_authenticated") is True:
        run_id = noc.get("run_id")
        if isinstance(run_id, str) and IDENTIFIER.fullmatch(run_id):
            try:
                # Import only after auth and signed source checks. Core is an
                # internal configured service, never a URL supplied by the caller.
                from shared.http import get_json
                core = get_json(os.getenv("CORE_URL", "http://aiops2-core:810"),
                                "/api/runs/" + run_id, timeout=3)
            except Exception:  # Upstream failure is UNKNOWN, never a successful correlation.
                core = None
    return JSONResponse(project_correlation(scenario, noc, core), headers=HEADERS)
