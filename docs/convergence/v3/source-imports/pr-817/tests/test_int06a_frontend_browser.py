"""Dedicated offline browser tests. No runtime endpoints or services."""
import os
from pathlib import Path
import unittest
from playwright.sync_api import expect
import test_explore_story_playwright_e2e as historical


class Int06AFrontend(unittest.TestCase):
    setUpClass = classmethod(historical.ExploreStoryChromiumE2E.setUpClass.__func__)
    tearDownClass = classmethod(historical.ExploreStoryChromiumE2E.tearDownClass.__func__)
    setUp = historical.ExploreStoryChromiumE2E.setUp
    tearDown = historical.ExploreStoryChromiumE2E.tearDown

    def test_home_widths_keyboard_and_selection(self):
        for width in (320, 768, 1440):
            with self.subTest(width=width):
                self.page.set_viewport_size({"width": width, "height": 900})
                self.page.goto(self.base + "/")
                self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
                self.page.keyboard.press("Tab")
                expect(self.page.locator(".portal-skip-link")).to_be_focused()
                self.page.locator("#incident-severity").select_option("P1")
                expect(self.page.locator("#incident-count")).to_contain_text("1 / 2")
                self.page.locator("#incident-reset").click()
                expect(self.page.locator("#incident-search")).to_be_focused()
                self.page.evaluate("""() => {
                    const row = document.getElementById('portal-runs').insertRow();
                    for (const value of ['RUN-TEST-A','TEST','UNKNOWN','-','DOM only'])
                        row.insertCell().textContent = value;
                }""")
                button = self.page.locator("button[data-run-select='RUN-TEST-A']")
                button.click()
                field = self.page.locator("#run-detail-id")
                expect(field).to_be_focused()
                field.fill("RUN-MANUAL")
                expect(self.page.locator("#run-selection-status")).to_contain_text("manuellement")
                button.click()
                self.page.evaluate("document.querySelector('[data-run-select=RUN-TEST-A]').parentNode.firstChild.textContent = 'RUN-TEST-B'")
                expect(field).to_have_value("")
                expect(self.page.locator("button[data-run-select='RUN-TEST-B']")).to_be_visible()
                if os.environ.get("AIOPS_E2E_ARTIFACT_DIR"):
                    target = Path(os.environ["AIOPS_E2E_ARTIFACT_DIR"])
                    target.mkdir(parents=True, exist_ok=True)
                    self.page.screenshot(path=str(target / f"int06a-home-{width}.png"), full_page=True)

    def test_mobile_provenance_and_workbench(self):
        self.page.set_viewport_size({"width": 320, "height": 844})
        self.page.goto(self.base + "/demo/acme-impact")
        expect(self.page.locator(".mobile-path")).to_be_visible()
        self.page.locator(".table-scroll").focus()
        expect(self.page.locator(".table-scroll")).to_be_focused()
        self.page.goto(self.base + "/demo/acme-incident-cockpit#evidence")
        expect(self.page.locator("#evidence + #workbench")).to_be_visible()
        expect(self.page.locator(".story-context")).to_contain_text("STORY_OFFLINE")
        expect(self.page.locator("body")).to_contain_text("9 MISSING")
