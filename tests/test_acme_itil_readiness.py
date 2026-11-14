"""ITIL transition readiness must never infer an effect from synthetic fixtures."""
import copy
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_impact_read_model import router
from portal.acme_itil_readiness import (
    REQUIRED, assess_synthetic_itil_readiness, build_synthetic_itil_readiness,
)
from portal.acme_lifecycle_read_model import build_synthetic_incident_lifecycle


def test_every_itil_transition_requires_missing_independent_proof():
    result = build_synthetic_itil_readiness()
    assert len(result["transitions"]) == len(REQUIRED) == 8
    assert result["authorized_transition_count"] == 0
    assert result["actual_glpi_ticket_updated"] is False
    assert result["temporal_execution_performed"] is False
    assert result["production_remediation_verified"] is False
    assert all(not t["authorized"] and t["readiness"] == "UNKNOWN"
               and t["missing_evidence"] == t["required_checkpoints"]
               for t in result["transitions"])
    assert result["transitions"][-1]["transition"] == "CLOSE_ITIL_AND_OPEN_PIR"


@pytest.mark.parametrize("field,value", [
    ("overall_qualification", "PASS"),
    ("runtime_attested", True),
    ("live_remediation_authorized", True),
    ("policy_disposition", "ALLOW_LIVE_ACTION"),
    ("orchestration_effect_state", "SUCCESS"),
    ("postcheck_state", "PASS"),
])
def test_laundered_lifecycle_rejected(field, value):
    model = build_synthetic_incident_lifecycle()
    model[field] = value
    with pytest.raises(ValueError, match="unqualified_itil_lifecycle"):
        assess_synthetic_itil_readiness(model)


def test_forged_stage_proof_rejected():
    model = copy.deepcopy(build_synthetic_incident_lifecycle())
    model["stages"][6]["evidence_state"] = "PASS"
    with pytest.raises(ValueError, match="unqualified_itil_stage"):
        assess_synthetic_itil_readiness(model)


def test_portal_api_readonly_and_invalid_fixture_denied():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/demo/acme-itil-readiness")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["authorized_transition_count"] == 0
    with patch("portal.acme_impact_read_model.build_acme_impact_read_model",
               return_value={"schema": "unqualified"}):
        denied = client.get("/api/demo/acme-itil-readiness")
    assert denied.status_code == 503
