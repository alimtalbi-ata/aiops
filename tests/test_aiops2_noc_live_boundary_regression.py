"""NOC cockpit regression: no synthetic evidence can be rendered as LIVE authority.

These tests exercise the standalone renderer only; they do not qualify a browser,
external evidence service, tenant ACL, or any operational connector.
"""
from copy import deepcopy

import pytest

from scripts.aiops2_noc_decision_cards import render_decision_cards
from test_aiops2_noc_decision_cards_contract import projection


@pytest.mark.parametrize("field,value", [
    ("policy_disposition", "ALLOW"),
    ("policy_disposition", "APPROVED"),
    ("runtime_attested", True),
    ("runtime_attested", None),
    ("live_remediation_authorized", True),
    ("live_remediation_authorized", None),
    ("impact_state", "ATTESTED"),
])
def test_decision_cannot_be_promoted_to_live(field, value):
    data = deepcopy(projection())
    data["decisions"][0][field] = value
    with pytest.raises(ValueError, match="unqualified_decision"):
        render_decision_cards(data)


@pytest.mark.parametrize("field,value", [
    ("schema", "aiops2.live-noc-decision.v1"),
    ("mode", "REPLAY"),
    ("scope", "EXTERNAL_IO"),
    ("runtime_attested", None),
    ("live_remediation_authorized", None),
    ("decisions", {}),
])
def test_projection_must_remain_offline_simulation(field, value):
    data = deepcopy(projection())
    data[field] = value
    with pytest.raises(ValueError, match="unqualified_projection"):
        render_decision_cards(data)


def test_rendered_action_is_text_not_executable_control():
    data = deepcopy(projection())
    data["decisions"][0]["next_noc_action"] = '<button onclick="alert(1)">RUN</button>'
    html = render_decision_cards(data)
    assert "&lt;button" in html
    assert "<button" not in html
    assert "<form" not in html
    assert "DENY_LIVE" in html
    assert "UNKNOWN — provenance non attestée" in html


def test_no_decisions_does_not_invent_incident():
    data = deepcopy(projection())
    data["decisions"] = []
    html = render_decision_cards(data)
    assert "Aucun incident synthétique calculé." in html
    assert "<article" not in html
    assert "LIVE non attesté" in html
