"""End-to-end synthetic lifecycle contract: no invented runtime evidence."""
import copy
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_impact_read_model import build_acme_impact_read_model, router
from portal.acme_lifecycle_read_model import (
    STAGES, build_synthetic_incident_lifecycle,
    project_synthetic_incident_lifecycle,
)


def test_complete_incident_to_itil_lifecycle_is_explicitly_unqualified():
    model = build_synthetic_incident_lifecycle()
    assert model["mode"] == "DEMO"
    assert len(model["stages"]) == len(STAGES) == 9
    assert [s["cue"] for s in model["stages"]] == [s[0] for s in STAGES]
    assert all(s["evidence_state"] == "UNKNOWN" for s in model["stages"])
    assert all(s["operational_transition_authorized"] is False for s in model["stages"])
    assert model["policy_disposition"] == "DENY_LIVE_ACTION"
    assert model["orchestration_effect_state"] == "NO_EFFECT_RECEIPT"
    assert model["postcheck_state"] == "UNKNOWN"
    assert model["live_remediation_authorized"] is False
    assert model["source_sha256"] == build_acme_impact_read_model()["source_sha256"]


@pytest.mark.parametrize("field,value", [
    ("runtime_attested", True),
    ("production_qualified", True),
    ("live_remediation_authorized", True),
    ("runtime_evidence_present", True),
    ("ticket_id", "42"),
    ("event_timestamp_utc", "2026-11-14T00:00:00Z"),
])
def test_runtime_claims_cannot_be_laundered_into_synthetic_lifecycle(field, value):
    impact = build_acme_impact_read_model()
    impact[field] = value
    with pytest.raises(ValueError, match="unqualified_synthetic_impact"):
        project_synthetic_incident_lifecycle(impact)


def test_checkpoint_cannot_claim_proof_without_independent_attestation():
    impact = copy.deepcopy(build_acme_impact_read_model())
    impact["checkpoint_evidence"][0]["status"] = "PASS"
    with pytest.raises(ValueError, match="unqualified_lifecycle_checkpoint"):
        project_synthetic_incident_lifecycle(impact)


def test_api_is_no_store_and_fail_closed():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/demo/acme-lifecycle")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["overall_qualification"] == "UNKNOWN"
    with patch("portal.acme_impact_read_model.build_acme_impact_read_model",
               return_value={"schema": "invalid"}):
        denied = client.get("/api/demo/acme-lifecycle")
    assert denied.status_code == 503
