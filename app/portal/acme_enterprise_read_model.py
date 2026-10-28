"""Canonical synthetic ACME enterprise projection for Explore and Story.

Read-only, no Core/GLPI/Twin network calls or LIVE evidence claims.
The six-CI v1 fixture remains the authoritative seed for both projections.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from portal.acme_fixture_contract import (
    expand_enterprise_fixture, load_fixture_bytes, validate_fixture,
)
from portal.acme_impact_read_model import (
    FIXTURE_PATH, HEADERS, _read_fixture_bytes_safely,
)

router = APIRouter()
SITES = (
    {"id": "PARIS-HQ", "name": "Paris — siège", "role": "HQ"},
    {"id": "LYON-DC", "name": "Lyon — datacenter", "role": "DATACENTER"},
    {"id": "LILLE-RETAIL", "name": "Lille — commerce", "role": "RETAIL"},
    {"id": "BORDEAUX-DR", "name": "Bordeaux — reprise", "role": "DR"},
)
SITE_IDS = tuple(site["id"] for site in SITES)
BASE_SITE = {
    "SAN-FABRIC-A": "LYON-DC", "SAN-FABRIC-B": "LYON-DC",
    "HOST-ESX-01": "LYON-DC", "VOL-PAY-01": "LYON-DC",
    "VM-PAY-01": "LYON-DC", "APP-PAY-01": "PARIS-HQ",
}
# Historical scenario clock, not observed event time.
HISTORY_UTC = (
    "2026-09-14T08:15:00Z", "2026-09-18T10:45:00Z",
    "2026-09-23T14:30:00Z", "2026-10-02T07:05:00Z",
    "2026-10-12T16:20:00Z", "2026-10-25T09:00:00Z",
)


def build_acme_enterprise_read_model() -> dict[str, Any]:
    """Build one validated, byte-anchored data source for both views."""
    raw = _read_fixture_bytes_safely(FIXTURE_PATH)
    seed = load_fixture_bytes(raw)
    validate_fixture(seed)
    expanded = expand_enterprise_fixture(seed)
    report = validate_fixture(expanded)
    site_map = {
        ci["id"]: BASE_SITE.get(ci["id"], SITE_IDS[index % len(SITE_IDS)])
        for index, ci in enumerate(expanded["ci"])
    }
    cis = [
        {**ci, "site_id": site_map[ci["id"]], "provenance": "SIMULATED_TARGET"}
        for ci in sorted(expanded["ci"], key=lambda item: item["id"])
    ]
    incidents = sorted(expanded["incidents"], key=lambda item: item["id"])
    events = []
    tickets = []
    for index, incident in enumerate(incidents):
        event_id = f"SIM-EVT-{index + 1:03}"
        ticket_id = f"SIM-GLPI-{index + 1:03}"
        events.append({
            "id": event_id, "incident_id": incident["id"], "ci_id": incident["ci"],
            "site_id": site_map[incident["ci"]],
            "scenario_timestamp_utc": HISTORY_UTC[index],
            "timestamp_provenance": "FIXED_SCENARIO_CLOCK_NOT_RUNTIME",
            "kind": "SYNTHETIC_ALERT", "mode": "DEMO",
        })
        tickets.append({
            "id": ticket_id, "incident_id": incident["id"], "event_id": event_id,
            "ci_id": incident["ci"], "status": "SIMULATED_NOT_IN_GLPI",
            "glpi_ticket_id": None, "core_run_id": None,
            "provenance": "SYNTHETIC_LABEL_NOT_A_GLPI_TICKET",
        })
    services = [
        {"id": ci["id"], "name": ci["name"], "depends_on": ci["depends_on"],
         "site_id": site_map[ci["id"]], "health": "UNKNOWN"}
        for ci in cis if ci["kind"] == "BusinessService"
    ]
    source_sha = hashlib.sha256(raw).hexdigest()
    canonical_data = {
        "sites": list(SITES), "ci": cis, "applications": services,
        "incidents": incidents, "events": events, "tickets": tickets,
        "impact_path": report["impact_path"],
    }
    dataset_sha = hashlib.sha256(
        json.dumps(canonical_data, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema": "aiops.acme.enterprise-read-model.v1",
        "fixture_schema": "aiops.acme.demo.v1",
        "organization": "ACME-DEMO", "mode": "DEMO",
        "provenance": "SIMULATED_TARGET",
        "source_artifact": "app/portal/acme-fixtures.json",
        "source_sha256": source_sha, "dataset_sha256": dataset_sha,
        "ci_count": len(cis), "incident_count": len(incidents),
        **canonical_data,
        "runtime_attested": False, "live_remediation_authorized": False,
        "backend_writes": False, "glpi_ticket_verified": False,
    }


def _read_or_503() -> dict[str, Any]:
    try:
        return build_acme_enterprise_read_model()
    except (OSError, UnicodeError, ValueError, ImportError, AttributeError) as exc:
        raise HTTPException(
            status_code=503, detail="synthetic_enterprise_fixture_unavailable_or_invalid"
        ) from exc


@router.get("/api/demo/acme-enterprise/explore")
def enterprise_explore():
    """Read the same canonical dataset as Story; no side effects."""
    return JSONResponse(content=_read_or_503(), headers=HEADERS)


@router.get("/api/demo/acme-enterprise/story")
def enterprise_story():
    """Identical data and IDs, not an independent invented story source."""
    return JSONResponse(content=_read_or_503(), headers=HEADERS)
