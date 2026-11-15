"""Chromium-only visual qualification for the isolated SIMULATION cockpit.

Run explicitly: python -m pytest -q tests/test_aiops2_noc_browser.py
Requires pytest-playwright and installed Chromium. No server, network or LIVE I/O.
Screenshots are local evidence, not proof of a deployed route.
"""
from pathlib import Path

import pytest

from scripts.aiops2_noc_decision_cards import render_decision_cards
from tests.test_aiops2_noc_decision_cards_contract import projection


@pytest.mark.parametrize("width", [320, 768, 1440])
def test_noc_cards_chromium_responsive_and_semantic(page, width, tmp_path):
    page.set_viewport_size({"width": width, "height": 900})
    page.set_content(render_decision_cards(projection()), wait_until="load")
    assert page.title() == "Cockpit NOC — SIMULATION"
    assert page.get_by_role("heading", name="Cockpit décisionnel — SIMULATION").count() == 1
    assert page.get_by_role("article", name="Incident INC-SIM-1").count() == 1
    assert page.get_by_text("DENY_LIVE").count() >= 1
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.get_by_text("san-01 → storage → payments").is_visible()
    page.screenshot(path=str(tmp_path / f"noc-simulation-{width}.png"), full_page=True)
