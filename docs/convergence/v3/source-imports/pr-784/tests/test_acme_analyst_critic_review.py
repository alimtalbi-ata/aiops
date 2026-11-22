"""Analyst/Critic hypotheses never qualify as independently verified evidence."""
import copy
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_impact_read_model import build_acme_impact_read_model
from portal.acme_analyst_critic_review import review_synthetic_analyst_critic


def test_hypothesis_critic_and_policy_remain_no_go():
    result = review_synthetic_analyst_critic(build_acme_impact_read_model())
    assert result["analysis_kind"] == "DETERMINISTIC_HYPOTHESIS_NOT_LLM"
    assert result["critic_disposition"] == "HOLD_FOR_HUMAN_REVIEW"
    assert result["runtime_citations_verified"] == 0
    assert result["missing_review_checkpoints"] == ["analyze", "approve", "verify"]
    assert result["policy_disposition"] == "DENY_LIVE_ACTION"
    assert result["operational_decision_authorized"] is False
    assert result["live_remediation_authorized"] is False


@pytest.mark.parametrize("path,value", [
    (("provider",), "LLM_ATTESTED"),
    (("live_execution",), True),
    (("backend_writes",), True),
    (("analyst", "status"), "VERIFIED"),
    (("critic", "decision"), "APPROVED"),
    (("policy", "decision"), "ALLOW_LIVE_ACTION"),
])
def test_forged_analyst_critic_or_policy_claims_rejected(path, value):
    impact = copy.deepcopy(build_acme_impact_read_model())
    target = impact["decision_preview"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError, match="unqualified_analyst_critic_preview"):
        review_synthetic_analyst_critic(impact)


def test_canonical_portal_route_read_only_and_fail_closed():
    with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
        from portal.main import app
    client = TestClient(app)
    result = client.get("/api/demo/acme-analyst-critic-review")
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    assert result.json()["runtime_citations_verified"] == 0
    with patch("portal.acme_impact_read_model.build_acme_impact_read_model",
               return_value={"schema": "invalid"}):
        denied = client.get("/api/demo/acme-analyst-critic-review")
    assert denied.status_code == 503
