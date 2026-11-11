"""Regression contract: browser E2E remains mandatory without flaky runner apt fetches."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_quality_gate_keeps_real_browser_e2e_without_apt_install():
    workflow = (ROOT / ".github/workflows/quality.yml").read_text(encoding="utf-8")
    assert "python -m playwright install chromium" in workflow
    assert "playwright install --with-deps chromium" not in workflow
    assert "test_explore_story_playwright_e2e.py" in workflow
    assert "Explore Story real Chromium to ephemeral portal E2E" in workflow
    assert "if: success()" in workflow


def test_chromium_preflight_keeps_actual_browser_launch():
    workflow = (ROOT / ".github/workflows/portal-chromium-preflight-diagnostic.yml").read_text(encoding="utf-8")
    assert "python -m playwright install chromium" in workflow
    assert "playwright install --with-deps chromium" not in workflow
    assert "p.chromium.launch(headless=True)" in workflow
    assert "page.locator(\"main\").inner_text()" in workflow
