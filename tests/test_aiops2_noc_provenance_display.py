"""Regression: a synthetic node list never becomes attested impact evidence."""
from copy import deepcopy

import pytest

from scripts.aiops2_noc_decision_cards import render_decision_cards
from test_aiops2_noc_decision_cards_contract import projection


def test_unverified_path_explicitly_unknown():
    html = render_decision_cards(projection())
    assert "UNKNOWN — provenance non attestée" in html
    assert "chemin proposé (simulation)" in html
    assert "source, fraîcheur et version du graphe UNKNOWN" in html
    assert "DENY_LIVE" in html
    assert "SIMULATION" in html


@pytest.mark.parametrize("field,value", [
    ("mode", "LIVE"),
    ("scope", "LIVE"),
    ("runtime_attested", True),
    ("live_remediation_authorized", True),
])
def test_no_live_promotion(field, value):
    data = deepcopy(projection())
    data[field] = value
    with pytest.raises(ValueError, match="unqualified_projection"):
        render_decision_cards(data)


def test_unsafe_html_in_path_escaped_even_when_unverified():
    data = deepcopy(projection())
    data["decisions"][0]["impact_paths"][0]["nodes"][0] = "<img src=x onerror=alert(1)>"
    html = render_decision_cards(data)
    assert "<img" not in html
    assert "&lt;img" in html
    assert "UNKNOWN — provenance non attestée" in html
