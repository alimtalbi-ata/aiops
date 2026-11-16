"""Negative Chromium boundary checks for offline NOC SIMULATION only.

Requires pytest-playwright and Chromium. No server, tenant or LIVE I/O.
The source branch inherits #719/#735; architect must reconcile before integration.
"""
from copy import deepcopy

import pytest

from scripts.aiops2_noc_decision_cards import render_decision_cards
from test_aiops2_noc_decision_cards_contract import projection


@pytest.mark.parametrize("width", [320, 768, 1440])
def test_no_actionable_live_controls_or_remote_resources(page, width):
    requested = []

    def block(route):
        requested.append(route.request.url)
        route.abort()

    page.route("**/*", block)
    page.set_viewport_size({"width": width, "height": 900})
    page.set_content(render_decision_cards(projection()), wait_until="load")
    assert page.get_by_role("main").count() == 1
    assert page.get_by_role("article", name="Incident INC-SIM-1").count() == 1
    assert page.get_by_text("DENY_LIVE").count() >= 1
    assert page.get_by_text("UNKNOWN — provenance non attestée", exact=False).count() >= 1
    assert page.locator("button, input, select, textarea, form, a[href]").count() == 0
    assert page.locator("script, iframe, object, embed").count() == 0
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert requested == []


def test_untrusted_noc_fields_never_become_markup_or_execution(page):
    data = deepcopy(projection())
    attack = "<img src='https://invalid.example/collect' onerror='alert(1)'>"
    item = data["decisions"][0]
    item["analyst"]["hypothesis"] = attack
    item["critic"]["disposition"] = attack
    item["next_noc_action"] = attack
    item["incident_id"] = "INC-SIM-1"
    attempted = []
    page.route("**/*", lambda route: (attempted.append(route.request.url), route.abort()))
    html = render_decision_cards(data)
    assert "&lt;img" in html
    page.set_content(html)
    assert page.locator("img, script, iframe").count() == 0
    assert page.get_by_text(attack, exact=False).count() == 3
    assert attempted == []
    assert page.get_by_text("DENY_LIVE").count() >= 1
