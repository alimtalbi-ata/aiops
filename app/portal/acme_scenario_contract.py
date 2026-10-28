"""Canonical read-only ACME scenario/event contract shared by Explore and Story.

All identifiers are synthetic labels derived from the validated local fixture.
This is not a Core Run, GLPI ticket, observed event, or runtime evidence.
"""
from __future__ import annotations

import re
from typing import Any

from portal.acme_fixture_contract import (
    SOURCE_INCIDENT_ID, TARGET_INCIDENT_ID, SOURCE_CI_ID, TARGET_CI_ID,
)

SCHEMA = "aiops.acme-scenario.v1"
CUES = ("detect", "correlate", "enrich", "analyze", "ticket",
        "approve", "simulate", "verify", "close")
PATH = (SOURCE_CI_ID, "HOST-ESX-01", "VM-PAY-01", TARGET_CI_ID)


def build_acme_scenario_contract(model: dict[str, Any]) -> dict[str, Any]:
    """Project one validated synthetic impact model; refuse any runtime promotion."""
    if type(model) is not dict:
        raise ValueError("invalid synthetic scenario source")
    digest = model.get("source_sha256")
    if type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("invalid synthetic source digest")
    if (model.get("provenance") != "SIMULATED_TARGET"
            or model.get("incident_id") != SOURCE_INCIDENT_ID
            or model.get("impact_incident_id") != TARGET_INCIDENT_ID
            or model.get("impact_path") != list(PATH)
            or model.get("run_id") != "SIM-ACME-" + digest[:16].upper()
            or model.get("simulation_ticket_id") != "SIM-GLPI-" + digest[:12].upper()
            or model.get("run_id_provenance") != "DERIVED_FROM_FIXTURE_SHA256_NOT_RUNTIME_RUN"
            or model.get("ticket_id") is not None
            or model.get("event_timestamp_utc") is not None
            or model.get("runtime_evidence_present") is not False
            or model.get("runtime_attested") is not False
            or model.get("production_qualified") is not False
            or model.get("live_remediation_authorized") is not False):
        raise ValueError("synthetic scenario invariants violated")

    checkpoints = model.get("checkpoint_evidence")
    if type(checkpoints) is not list or len(checkpoints) != len(CUES):
        raise ValueError("invalid synthetic checkpoint sequence")
    events = []
    for sequence, (cue, checkpoint) in enumerate(zip(CUES, checkpoints), start=1):
        if (type(checkpoint) is not dict
                or checkpoint.get("cue") != cue
                or checkpoint.get("status") != "MISSING"
                or checkpoint.get("screenshot_sha256") is not None
                or checkpoint.get("event_timestamp_utc") is not None
                or checkpoint.get("runtime_authenticated") is not False
                or checkpoint.get("source") != "CHECKPOINT_CONTRACT_ONLY_NO_CAPTURE"):
            raise ValueError("unqualified checkpoint")
        service, view = checkpoint.get("service"), checkpoint.get("view")
        if (type(service) is not str or type(view) is not str
                or re.fullmatch(r"[a-z][a-z0-9_]{1,49}", service) is None
                or re.fullmatch(r"[a-z][a-z0-9_]{1,49}", view) is None):
            raise ValueError("invalid synthetic checkpoint label")
        events.append({
            "id": f"SIM-EVT-ACME-{sequence:03d}",
            "sequence": sequence, "cue": cue, "service": service, "view": view,
            "incident_id": SOURCE_INCIDENT_ID,
            "impact_incident_id": TARGET_INCIDENT_ID,
            "status": "MISSING", "event_timestamp_utc": None,
            "provenance": "SIMULATED_TARGET",
        })

    return {
        "schema": SCHEMA, "fixture_schema": "aiops.acme.demo.v1",
        "organization": "ACME-DEMO", "mode": "DEMO",
        "state": "SIMULATED_UNVERIFIED", "provenance": "SIMULATED_TARGET",
        "source_sha256": digest,
        "scenario": {
            "run_id": model["run_id"],
            "run_id_provenance": "DERIVED_FROM_FIXTURE_SHA256_NOT_RUNTIME_RUN",
            "incident_id": SOURCE_INCIDENT_ID,
            "impact_incident_id": TARGET_INCIDENT_ID,
            "impact_path": list(PATH),
            "ticket_id": None, "event_timestamp_utc": None,
            "simulation_ticket_id": model["simulation_ticket_id"],
            "simulation_ticket_provenance": "SYNTHETIC_LABEL_NOT_A_GLPI_TICKET",
        },
        "events": events,
        "event_count": len(events),
        "runtime_attested": False, "production_qualified": False,
        "live_remediation_authorized": False, "backend_writes": False,
    }
