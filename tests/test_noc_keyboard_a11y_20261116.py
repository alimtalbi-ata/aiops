"""Keyboard and semantic browser gate for the isolated NOC prototype.

Run: python -m unittest tests/test_noc_keyboard_a11y_20261116.py
Artifacts: NOC_CAPTURE_DIR=/tmp/noc-captures (optional)
Only local HTML; network requests are aborted. No LIVE effects.
"""
import hashlib
import json
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs/ux/prototypes/noc_decision_sandbox_20261116.html"


class NocKeyboardAccessibility(unittest.TestCase):
    def test_keyboard_semantics_and_capture(self):
        from playwright.sync_api import sync_playwright

        self.assertTrue(HTML.is_file(), f"Exact source missing: {HTML}")
        source = HTML.read_bytes()
        out = Path(os.environ.get("NOC_CAPTURE_DIR", "/tmp/aiops2-noc-a11y-captures"))
        out.mkdir(parents=True, exist_ok=True)
        manifest = {
            "qualification": "LOCAL_BROWSER_ONLY",
            "source_sha256": hashlib.sha256(source).hexdigest(),
            "source_git_sha": os.environ.get("NOC_SOURCE_GIT_SHA", "UNKNOWN"),
            "mode": "SIMULATION",
            "policy": "DENY_LIVE",
            "captures": [],
        }
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
            try:
                for width in (320, 768, 1440):
                    page = browser.new_page(viewport={"width": width, "height": 900})
                    requests = []
                    page.route("**/*", lambda route: (requests.append(route.request.url), route.abort()))
                    page.set_content(source.decode("utf-8"), wait_until="load")
                    self.assertEqual(page.get_by_role("main").count(), 1)
                    self.assertEqual(page.get_by_role("heading", level=1).count(), 1)
                    self.assertEqual(page.locator("section[aria-labelledby]").count(), 6)
                    for section in page.locator("section[aria-labelledby]").all():
                        label = section.get_attribute("aria-labelledby")
                        self.assertTrue(label)
                        self.assertEqual(section.locator(f'h2[id="{label}"]').count(), 1)
                    self.assertIn("UNKNOWN", page.locator("body").inner_text())
                    self.assertIn("DENY_LIVE", page.locator("body").inner_text())
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                    page.keyboard.press("Tab")
                    self.assertEqual(page.evaluate("document.activeElement.id"), "prepare")
                    self.assertNotEqual(page.evaluate("getComputedStyle(document.activeElement).outlineStyle"), "none")
                    page.keyboard.press("Enter")
                    self.assertIn("Aucune transmission", page.get_by_role("status").inner_text())
                    self.assertEqual(requests, [])
                    capture = out / f"noc-a11y-{width}.png"
                    page.screenshot(path=str(capture), full_page=True)
                    manifest["captures"].append({
                        "width": width,
                        "path": capture.name,
                        "sha256": hashlib.sha256(capture.read_bytes()).hexdigest(),
                        "bytes": capture.stat().st_size,
                        "network_requests": len(requests),
                    })
                    page.close()
            finally:
                browser.close()
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        self.assertEqual(len(manifest["captures"]), 3)


if __name__ == "__main__":
    unittest.main()
