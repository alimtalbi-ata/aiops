"""Evidence requests are not runtime evidence or authorization."""
import copy
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_evidence_collection_plan import (
    EVIDENCE_REQUIREMENTS, build_synthetic_evidence_collection_plan,
    plan_synthetic_evidence_collection,
)
from portal.acme_lifecycle_read_model import build_synthetic_incident_lifecycle


def test_all_nine_checkpoints_request_independent_proof_without_receipts():
    result = build_synthetic_evidence_collection_plan()
    assert result["requested_count"] == 9
    assert result["verified_count"] == 0
    assert {r["checkpoint"] for r in result["requests"]} == set(EVIDENCE_REQUIREMENTS)
    assert all(r["evidence_state"] == "MISSING" and r["submitted_evidence"] is None
               and not r["attested"] and not r["qualifies_runtime"]
               for r in result["requests"])
    assert all({"observed_at", "source_id", "content_sha256"} <= set(r["required_metadata"])
               for r in result["requests"])
    assert result["evidence_acceptance_enabled"] is False
    assert result["outbound_collection_enabled"] is False
    assert result["glpi_write_enabled"] is False
    assert result["temporal_execution_enabled"] is False
    assert result["live_remediation_authorized"] is False


def test_forged_lifecycle_evidence_rejected():
    model = copy.deepcopy(build_synthetic_incident_lifecycle())
    model["stages"][0]["evidence_state"] = "PASS"
    with pytest.raises(ValueError, match="unqualified_itil_stage"):
        plan_synthetic_evidence_collection(model)


def test_canonical_portal_mounts_read_only_evidence_api_and_fails_closed():
    with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
        from portal.main import app
    client = TestClient(app)
    response = client.get("/api/demo/acme-evidence-plan")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["verified_count"] == 0
    with patch("portal.acme_impact_read_model.build_acme_impact_read_model",
               return_value={"schema": "invalid"}):
        denied = client.get("/api/demo/acme-evidence-plan")
    assert denied.status_code == 503


def test_canonical_operator_evidence_page_is_static_and_denies_invalid_source():
    with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
        from portal.main import app
    client = TestClient(app)
    page = client.get("/demo/acme-evidence-plan")
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    assert "SIMULATION LOCALE UNIQUEMENT" in page.text
    assert "NO-GO LIVE" in page.text
    assert "ALERT_STATE" in page.text
    assert "INDEPENDENT_POSTCHECK" in page.text
    assert "Preuves vérifiées : 0 / 9" in page.text
    assert page.text.count("<tr><th scope='row'>") == 9
    assert "<script" not in page.text.lower()
    assert "<form" not in page.text.lower()
    with patch("portal.acme_impact_read_model.build_acme_impact_read_model",
               return_value={"schema": "invalid"}):
        denied = client.get("/demo/acme-evidence-plan")
    assert denied.status_code == 503
