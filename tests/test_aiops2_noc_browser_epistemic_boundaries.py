"""Browser assertions for epistemic boundaries in the offline NOC cockpit.

No network, host, LIVE or production fixtures. Requires pytest-playwright.
"""
from copy import deepcopy

import pytest

from scripts.aiops2_noc_decision_cards import render_decision_cards
from test_aiops2_noc_decision_cards_contract import projection


@pytest.mark.parametrize("width", [320, 768, 1440])
def test_unknown_impact_is_visible_to_assistive_tree(page, width):
    p = deepcopy(projection())
    page.set_viewport_size({"width": width, "height": 900})
    external = []
    page.route("**/*", lambda route: (external.append(route.request.url), route.abort()))
    page.set_content(render_decision_cards(p))
    main = page.get_by_role("main")
    assert main.count() == 1
    assert page.get_by_role("article", name="Incident INC-SIM-1").count() == 1
    assert main.get_by_text("UNKNOWN — provenance non attestée", exact=False).count() >= 1
    assert main.get_by_text("DENY_LIVE").count() >= 1
    assert main.get_by_text("Hypothèse Analyst").count() >= 1
    assert main.get_by_text("Réserve Critic").count() >= 1
    assert main.get_by_text("Incertitude").count() >= 1
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert external == []


def test_untrusted_impact_node_cannot_inject_html_or_network(page):
    p = deepcopy(projection())
    marker = "<img src='https://invalid.example/beacon' onerror='alert(1)'>"
    p["decisions"][0]["impact_paths"][0]["nodes"][1] = marker
    requested = []
    page.route("**/*", lambda route: (requested.append(route.request.url), route.abort()))
    page.set_content(render_decision_cards(p))
    assert page.locator("img, iframe, script, object, embed").count() == 0
    assert page.get_by_text(marker, exact=False).count() >= 1
    assert page.get_by_text("DENY_LIVE").count() >= 1
    assert requested == []
