"""Offline safety and accessibility source contracts for candidate NOC cards."""
import pytest
from scripts.aiops2_noc_decision_cards import render_decision_cards


def projection():
    return {
        "schema": "aiops2.synthetic-noc-decision.v1",
        "mode": "SIMULATION", "scope": "OFFLINE_NO_EXTERNAL_IO",
        "runtime_attested": False, "live_remediation_authorized": False,
        "decisions": [{
            "incident_id": "<script>alert(1)</script>", "priority": "P1",
            "service_id": "payments", "event_count": 2,
            "impact_state": "SOURCED_SYNTHETIC_PATH",
            "impact_paths": [{"nodes": ["san-01", "storage", "payments"]}],
            "analyst": {"hypothesis": "storage"}, "critic": {
                "disposition": "REVIEW", "root_cause_confirmed": False},
            "next_noc_action": "REVIEW_SYNTHETIC_EVIDENCE",
            "policy_disposition": "DENY_LIVE",
            "runtime_attested": False, "live_remediation_authorized": False,
        }]
    }


def test_accessible_responsive_simulation():
    html = render_decision_cards(projection())
    assert "SIMULATION" in html and "DENY_LIVE" in html
    assert "san-01 → storage → payments" in html
    assert "viewport" in html and "grid-template-columns" in html
    assert "<main>" in html and "<article" in html and "<dl>" in html
    assert "<script>" not in html and "&lt;script&gt;" in html


@pytest.mark.parametrize("field,value", [
    ("mode", "LIVE"), ("runtime_attested", True),
    ("live_remediation_authorized", True), ("scope", "LIVE"),
])
def test_fail_closed_projection(field, value):
    p = projection()
    p[field] = value
    with pytest.raises(ValueError):
        render_decision_cards(p)


def test_fail_closed_policy_and_unknown_path():
    p = projection()
    p["decisions"][0]["policy_disposition"] = "ALLOW_LIVE"
    with pytest.raises(ValueError):
        render_decision_cards(p)
    p = projection()
    p["decisions"][0]["impact_state"] = "UNKNOWN"
    with pytest.raises(ValueError):
        render_decision_cards(p)
