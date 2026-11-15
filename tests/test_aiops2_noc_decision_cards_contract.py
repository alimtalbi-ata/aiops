"""Regression contracts for offline NOC decision-card safety."""
from copy import deepcopy
import pytest
def projection():
    return {
        "schema": "aiops2.synthetic-noc-decision.v1",
        "mode": "SIMULATION", "scope": "OFFLINE_NO_EXTERNAL_IO",
        "runtime_attested": False, "live_remediation_authorized": False,
        "decisions": [{
            "incident_id": "INC-SIM-1", "priority": "P1", "service_id": "payments",
            "event_count": 2, "impact_state": "SOURCED_SYNTHETIC_PATH",
            "impact_paths": [{"nodes": ["san-01", "storage", "payments"]}],
            "analyst": {"hypothesis": "storage"},
            "critic": {"disposition": "REVIEW", "root_cause_confirmed": False},
            "next_noc_action": "REVIEW_SYNTHETIC_EVIDENCE",
            "policy_disposition": "DENY_LIVE", "runtime_attested": False,
            "live_remediation_authorized": False,
        }],
    }

from scripts.aiops2_noc_decision_cards import render_decision_cards


@pytest.mark.parametrize("nodes", [[], ["san-01"], ["san-01", ""], ["san-01", None], ["san-01", 7]])
def test_reject_invalid_sourced_path_nodes(nodes):
    p = deepcopy(projection())
    p["decisions"][0]["impact_paths"][0]["nodes"] = nodes
    with pytest.raises(ValueError, match="invalid_path_nodes"):
        render_decision_cards(p)


@pytest.mark.parametrize("count", [None, 0, -1, True, "2", 2.5])
def test_reject_invalid_alert_counts(count):
    p = deepcopy(projection())
    p["decisions"][0]["event_count"] = count
    with pytest.raises(ValueError, match="invalid_correlated_alert_count"):
        render_decision_cards(p)


def test_structured_analyst_critic_and_uncertainty():
    html = render_decision_cards(projection())
    assert "Hypothèse Analyst</dt><dd>storage</dd>" in html
    assert "Réserve Critic</dt><dd>REVIEW — cause racine non confirmée</dd>" in html
    assert "Incertitude</dt>" in html
    assert "&#x27;hypothesis&#x27;" not in html


@pytest.mark.parametrize("section,key", [("analyst", "hypothesis"), ("critic", "disposition")])
def test_missing_assessment_fails_closed(section, key):
    p = deepcopy(projection())
    p["decisions"][0][section][key] = ""
    with pytest.raises(ValueError, match="missing_analyst_critic_assessment"):
        render_decision_cards(p)
