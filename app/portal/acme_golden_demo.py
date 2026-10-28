"""Authenticated Golden DEMO launcher bound to the validated local ACME fixture.

This is a synthetic Core write path, never a LIVE endpoint or a GLPI ticket
creator. Core responses are checked before advancing to the next write.
"""
from __future__ import annotations

import hmac
import os
import re

from fastapi import HTTPException

from portal.acme_impact_read_model import build_acme_impact_read_model

RUN_ID = re.compile(r"RUN-[A-Za-z0-9][A-Za-z0-9_.-]{1,95}\Z")
SCENARIO_ID = "SCN-GOLDEN-PAYMENT-P1"  # Existing seeded Core scenario, not fixture CI IDs.


def require_demo_auth(authorization: str | None) -> None:
    """Dedicated DEMO write credential; never accept the internal Core token."""
    configured = os.getenv("AIOPS_PORTAL_DEMO_TOKEN", "")
    privileged = (
        os.getenv("AIOPS_INTERNAL_TOKEN", ""),
        os.getenv("AIOPS_ADMIN_TOKEN", ""),
        os.getenv("ADMIN_TOKEN", ""),
    )
    if (not isinstance(configured, str) or len(configured) < 32 or
            not configured.isascii() or any(c.isspace() for c in configured) or
            any(token and hmac.compare_digest(configured, token)
                for token in privileged)):
        raise HTTPException(503, "demo_write_access_not_configured")
    supplied = (authorization or "").removeprefix("Bearer ")
    if (not authorization or not authorization.startswith("Bearer ") or
            not hmac.compare_digest(supplied, configured)):
        raise HTTPException(401, "demo_write_access_denied")


def launch_acme_golden_demo(post_json, core_url: str) -> dict:
    """Perform only the existing Core DEMO incident/run/execute sequence.

    This function is called only after require_demo_auth at the API boundary.
    A local fixture label is not the canonical Core Incident ID, and neither
    a Core response nor an HTTP success attests any downstream execution.
    """
    model = build_acme_impact_read_model()
    if (model.get("provenance") != "SIMULATED_TARGET" or
            model.get("runtime_attested") is not False or
            model.get("live_remediation_authorized") is not False or
            model.get("ticket_id") is not None or
            model.get("incident_id") != "ACME-DEMO-SAN-001" or
            model.get("impact_incident_id") != "ACME-DEMO-PAY-002"):
        raise ValueError("invalid synthetic Golden DEMO fixture")
    expected_incident = "INC-" + model["incident_id"]
    incident = post_json(core_url, "/api/incidents", {
        "external_id": model["incident_id"],
        "title": "ACME SAN P1 -> Payments P2 (synthetic Golden Demo)",
        "severity": "P1",
        "service_id": "ACME-SVC-PAYMENTS",
        "source": "portal-acme-demo",
        "synthetic": True,
        "payload": {
            "fixture_sha256": model["source_sha256"],
            "fixture_source_incident_id": model["incident_id"],
            "fixture_impact_incident_id": model["impact_incident_id"],
            "provenance": "SIMULATED_TARGET",
        },
    })
    if (not isinstance(incident, dict) or
            incident.get("incident_id") != expected_incident or
            incident.get("synthetic") is not True):
        raise ValueError("Core incident identity or synthetic flag mismatch")
    run = post_json(core_url, "/api/runs", {
        "mode": "DEMO",
        "scenario_id": SCENARIO_ID,
        "incident_id": expected_incident,
        "idempotency_key": "DEMO-ACME-SAN-PAY-" + model["source_sha256"][:16],
    })
    if (not isinstance(run, dict) or run.get("mode") != "DEMO" or
            RUN_ID.fullmatch(run.get("run_id", "")) is None):
        raise ValueError("Core DEMO run identity or mode mismatch")
    run_id = run["run_id"]
    executed = post_json(core_url, "/api/runs/" + run_id + "/execute", None)
    if not isinstance(executed, dict) or executed.get("run_id") != run_id:
        raise ValueError("Core execution receipt identity mismatch")
    return {
        "run_id": run_id,
        "canonical_incident_id": expected_incident,
        "fixture_incident_id": model["incident_id"],
        "fixture_impact_incident_id": model["impact_incident_id"],
        "fixture_sha256": model["source_sha256"],
        "scenario_id": SCENARIO_ID,
        "mode": "DEMO",
        "ticket_id": None,
        "execution_request_accepted": True,
        "runtime_attested": False,
        "production_qualified": False,
        "live_remediation_authorized": False,
        "provenance": "CORE_DEMO_REQUEST_NOT_RUNTIME_ATTESTATION",
    }
