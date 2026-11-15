"""Offline Chromium qualification for the isolated NOC SIMULATION renderer.

Run: python -m pytest -q tests/test_aiops2_noc_browser_a11y.py
Optional durable screenshots: NOC_SCREENSHOT_DIR=/safe/path (no network or LIVE).
Each PNG gets a SHA256 sidecar. No screenshot is an attestation of a runtime route.
"""
import hashlib
import os
from pathlib import Path

import pytest

from scripts.aiops2_noc_decision_cards import render_decision_cards
from test_aiops2_noc_decision_cards_contract import projection


@pytest.mark.parametrize("width", [320, 768, 1440])
def test_offline_decision_cockpit_accessibility_and_capture(page, width, tmp_path):
    # Block accidental external requests even if a future renderer adds assets.
    attempted = []
    def deny_external(route):
        attempted.append(route.request.url)
        route.abort()
    page.route("**/*", deny_external)
    page.set_viewport_size({"width": width, "height": 900})
    page.set_content(render_decision_cards(projection()), wait_until="load")

    assert page.locator("html").get_attribute("lang") == "fr"
    assert page.get_by_role("main").count() == 1
    assert page.get_by_role("heading", level=1).count() == 1
    assert page.get_by_role("region", name="Incidents calculés").count() == 1
    assert page.get_by_role("article", name="Incident INC-SIM-1").count() == 1
    assert page.get_by_role("status").get_by_text("LIVE non attesté", exact=False).is_visible()
    assert page.get_by_text("UNKNOWN — provenance non attestée", exact=False).is_visible()
    assert page.get_by_text("DENY_LIVE").count() >= 1
    assert page.get_by_text("san-01 → storage → payments").is_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert attempted == []

    output = Path(os.environ["NOC_SCREENSHOT_DIR"]) if os.getenv("NOC_SCREENSHOT_DIR") else tmp_path
    output.mkdir(parents=True, exist_ok=True)
    png = output / f"noc-offline-{width}.png"
    page.screenshot(path=str(png), full_page=True)
    (output / f"{png.name}.sha256").write_text(
        f"{hashlib.sha256(png.read_bytes()).hexdigest()}  {png.name}\n", encoding="ascii"
    )


def test_noc_text_zoom_without_horizontal_overflow(page):
    page.set_viewport_size({"width": 320, "height": 900})
    page.set_content(render_decision_cards(projection()))
    page.add_style_tag(content="html { font-size: 200%; }")
    assert page.get_by_role("heading", level=1).is_visible()
    assert page.get_by_text("DENY_LIVE").count() >= 1
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
