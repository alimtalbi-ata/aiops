"""A handoff draft must remain detached from GLPI and LIVE actions."""
import copy
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_impact_read_model import build_acme_impact_read_model
from portal.acme_itil_draft import build_synthetic_itil_handoff_draft


def test_deterministic_inert_itil_handoff():
    impact = build_acme_impact_read_model()
    draft = build_synthetic_itil_handoff_draft(impact)
    assert draft == build_synthetic_itil_handoff_draft(impact)
    assert draft["source_sha256"] == impact["source_sha256"]
    assert len(draft["draft_sha256"]) == 64
    assert draft["content"]["source_incident"] == impact["incident_id"]
    assert draft["content"]["affected_business_incident"] == impact["impact_incident_id"]
    assert len(draft["content"]["required_evidence"]) == 9
    assert draft["glpi_ticket_id"] is None
    assert draft["glpi_payload"] is None
    assert draft["glpi_write_performed"] is False
    assert draft["human_approved"] is False
    assert draft["itil_transition_authorized"] is False
    assert draft["live_remediation_authorized"] is False


@pytest.mark.parametrize("path,value", [
    (("runtime_attested",), True),
    (("decision_preview", "policy", "decision"), "ALLOW_LIVE_ACTION"),
    (("decision_preview", "critic", "decision"), "APPROVED"),
    (("checkpoint_evidence", 0, "status"), "PASS"),
])
def test_forged_authority_rejected(path, value):
    impact = copy.deepcopy(build_acme_impact_read_model())
    target = impact
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        build_synthetic_itil_handoff_draft(impact)


def test_canonical_portal_draft_endpoint_is_read_only_and_fail_closed():
    with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
        from portal.main import app
    client = TestClient(app)
    response = client.get("/api/demo/acme-itil-handoff-draft")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["glpi_payload"] is None
    with patch("portal.acme_impact_read_model.build_acme_impact_read_model",
               return_value={"schema": "invalid"}):
        assert client.get("/api/demo/acme-itil-handoff-draft").status_code == 503
