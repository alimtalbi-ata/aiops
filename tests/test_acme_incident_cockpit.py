"""A unified synthetic cockpit cannot mix snapshots or promote absent proof."""
import copy
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_impact_read_model import build_acme_impact_read_model
from portal.acme_incident_cockpit import project_synthetic_incident_cockpit


def test_cockpit_is_single_fixture_consistent_and_never_authorized():
    impact = build_acme_impact_read_model()
    result = project_synthetic_incident_cockpit(impact)
    assert result["source_sha256"] == impact["source_sha256"]
    assert result["incident_id"] == impact["incident_id"]
    assert result["business_impact_incident_id"] == impact["impact_incident_id"]
    assert result["lifecycle"]["source_sha256"] == result["evidence_plan"]["source_sha256"]
    assert result["itil_readiness"]["source_sha256"] == result["analyst_critic_review"]["source_sha256"]
    assert len(result["lifecycle"]["stages"]) == 9
    assert len(result["itil_readiness"]["transitions"]) == 8
    assert result["evidence_plan"]["requested_count"] == 9
    assert result["evidence_plan"]["verified_count"] == 0
    assert result["analyst_critic_review"]["runtime_citations_verified"] == 0
    assert result["overall_qualification"] == "UNKNOWN"
    assert result["live_remediation_authorized"] is False


@pytest.mark.parametrize("path,value", [
    (("runtime_attested",), True),
    (("decision_preview", "critic", "decision"), "APPROVED"),
    (("decision_preview", "policy", "decision"), "ALLOW_LIVE_ACTION"),
    (("checkpoint_evidence", 0, "status"), "PASS"),
])
def test_cockpit_rejects_forged_runtime_or_decision(path, value):
    impact = copy.deepcopy(build_acme_impact_read_model())
    target = impact
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        project_synthetic_incident_cockpit(impact)


def test_canonical_portal_cockpit_endpoint_fail_closed():
    with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
        from portal.main import app
    client = TestClient(app)
    response = client.get("/api/demo/acme-incident-cockpit")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["overall_qualification"] == "UNKNOWN"
    with patch("portal.acme_impact_read_model.build_acme_impact_read_model",
               return_value={"schema": "invalid"}):
        assert client.get("/api/demo/acme-incident-cockpit").status_code == 503


def test_canonical_operator_cockpit_page_contains_all_gates_and_no_actions():
    with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
        from portal.main import app
    client = TestClient(app)
    page = client.get("/demo/acme-incident-cockpit")
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    assert "NO-GO LIVE" in page.text
    assert "SAN P1" in page.text and "Payments P2" in page.text
    assert "HOLD_FOR_HUMAN_REVIEW" in page.text
    assert "DENY_LIVE_ACTION" in page.text
    assert "0 / 9" in page.text
    assert page.text.count("<tr><th scope='row'>") == 17
    assert "<script" not in page.text.lower()
    assert "<form" not in page.text.lower()
    with patch("portal.acme_impact_read_model.build_acme_impact_read_model",
               return_value={"schema": "invalid"}):
        assert client.get("/demo/acme-incident-cockpit").status_code == 503


def test_html_renderer_rejects_forged_success():
    from portal.acme_incident_cockpit_html import render_synthetic_cockpit_html
    cockpit = project_synthetic_incident_cockpit(build_acme_impact_read_model())
    cockpit["itil_readiness"]["transitions"][0]["authorized"] = True
    with pytest.raises(ValueError, match="unqualified_cockpit_details"):
        render_synthetic_cockpit_html(cockpit)
