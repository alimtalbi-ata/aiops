"""Synthetic GAMMA browser acceptance; run on isolated hosted runner."""
import unittest
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

class GammaAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(Path(__file__).resolve().parent)))
        cls.addClassCleanup(cls.server.server_close)
        thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        thread.start()
        cls.addClassCleanup(thread.join, 5)
        cls.addClassCleanup(cls.server.shutdown)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/index.html"
        cls.pw = sync_playwright().start()
        cls.addClassCleanup(cls.pw.stop)
        cls.browser = cls.pw.chromium.launch()
        cls.addClassCleanup(cls.browser.close)
    def setUp(self):
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.requests = []
        self.allowed = []
        self.blocked = []
        self.errors = []
        self.page.on("request", lambda r: self.requests.append((r.method, r.url)))
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        def gate(route):
            request = route.request
            entry = (request.method, request.url)
            if entry == ("GET", self.url) and request.is_navigation_request():
                self.allowed.append(entry)
                route.continue_()
            else:
                self.blocked.append(entry)
                route.abort()
        self.page.route("**/*", gate)
        self.page.goto(self.url)
    def test_run_selection_and_refusal(self):
        p = self.page
        self.assertIn("STORAGE", p.locator("#run-result").inner_text())
        p.locator("#policy").click()
        self.assertIn("DENIED", p.locator("#decision").inner_text())
        p.locator("#run-choice").select_option("network")
        self.assertIn("NETWORK", p.locator("#run-result").inner_text())
        self.assertEqual(p.locator("#decision").inner_text(), "No action requested.")
        self.assertEqual(self.allowed, [("GET", self.url)])
        self.assertEqual(self.blocked, [], "Unexpected attempted requests (blocked before network)")
        self.assertEqual(self.requests, [("GET", self.url)])
        self.assertFalse(self.errors)
    def test_admission_projection_and_run_reset(self):
        p = self.page
        receipt = p.locator("#admission")
        projection = p.locator("#admission-result")
        self.assertIn("UNKNOWN", projection.inner_text())
        for state, expected in (
            ("accept", "ACCEPT — synthetic event admitted; evidence MISSING."),
            ("duplicate", "DUPLICATE — synthetic replay; no additional evidence."),
            ("refused", "REFUSED — synthetic storage unavailable; evidence UNKNOWN."),
            ("unknown", "UNKNOWN — no admission receipt."),
        ):
            with self.subTest(state=state):
                receipt.select_option(state)
                self.assertEqual(projection.inner_text(), expected)
                self.assertIn("unverified", p.locator("#evidence").inner_text())
                self.assertIn("Runtime attested: false", p.locator("#evidence").inner_text())
        receipt.select_option("accept")
        p.locator("#run-choice").select_option("network")
        self.assertEqual(receipt.input_value(), "unknown")
        self.assertEqual(projection.inner_text(), "UNKNOWN — no admission receipt.")
        self.assertEqual(p.locator("#decision").inner_text(), "No action requested.")
        self.assertEqual(self.allowed, [("GET", self.url)])
        self.assertEqual(self.blocked, [])
        self.assertEqual(self.requests, [("GET", self.url)])
        self.assertFalse(self.errors)
    def test_keyboard(self):
        p = self.page
        for target in ["#incident", "#run", "#evidence", "#itsm"]:
            p.keyboard.press("Tab")
            self.assertEqual(p.evaluate("document.activeElement.getAttribute('href')"), target)
        p.keyboard.press("Enter")
        self.assertTrue(p.url.endswith("#itsm"))
        # Navigate to the canonical fragment-free URL for deterministic Tab order.
        p.goto(self.url)
        self.assertEqual(p.url, self.url)
        self.assertEqual(p.evaluate("document.activeElement.tagName"), "BODY")
        for target in ("#incident", "#run", "#evidence", "#itsm"):
            p.keyboard.press("Tab")
            self.assertEqual(p.evaluate("document.activeElement.getAttribute('href')"), target)
        p.keyboard.press("Tab")
        self.assertEqual(p.evaluate("document.activeElement.id"), "run-choice")
        p.keyboard.press("ArrowDown")
        self.assertIn("NETWORK", p.locator("#run-result").inner_text())
        p.keyboard.press("Tab")
        self.assertEqual(p.evaluate("document.activeElement.id"), "admission")
        p.keyboard.press("Tab")
        self.assertEqual(p.evaluate("document.activeElement.id"), "policy")
        self.assertTrue(p.locator("#policy").evaluate("(el) => el.matches(':focus-visible')"))
        p.keyboard.press("Enter")
        self.assertIn("DENIED", p.locator("#decision").inner_text())
        # Reverse and forward traversal must remain keyboard reachable after activation.
        for key, expected in (("Shift+Tab", "admission"), ("Shift+Tab", "run-choice"),
                              ("Tab", "admission"), ("Tab", "policy")):
            p.keyboard.press(key)
            self.assertEqual(p.evaluate("document.activeElement.id"), expected)
            self.assertTrue(p.evaluate("document.activeElement.matches(':focus-visible')"),
                            f"Focus invisible after {key} to {expected}")
        self.assertEqual(self.allowed, [("GET", self.url)] * 2)
        self.assertEqual(self.requests, [("GET", self.url)] * 2)
        self.assertEqual(self.blocked, [], "Keyboard flow attempted an unexpected request")
        self.assertFalse(self.errors, "Keyboard flow raised a JavaScript error")
    def test_accessibility_semantics(self):
        p = self.page
        self.assertEqual(p.locator("html").get_attribute("lang"), "en")
        self.assertEqual(p.locator('nav[aria-label="Incident sections"] a').count(), 4)
        for control in ("run-choice", "admission"):
            with self.subTest(control=control):
                self.assertEqual(p.locator(f'label[for="{control}"]').count(), 1)
                self.assertEqual(p.locator(f'#{control}').count(), 1)
        for status in ("run-result", "admission-result", "decision"):
            with self.subTest(status=status):
                self.assertEqual(p.locator(f'#{status}').get_attribute("role"), "status")
                self.assertTrue(p.locator(f'#{status}').inner_text().strip())
        for width in (320, 1280, 1920):
            with self.subTest(width=width):
                p.set_viewport_size({"width": width, "height": 900})
                # Canonical navigation clears any fragment and starts at BODY.
                # No programmatic .focus() in the keyboard oracle.
                p.goto(self.url)
                self.assertEqual(p.url, self.url)
                self.assertEqual(p.evaluate("document.activeElement.tagName"), "BODY")
                for expected in ("#incident", "#run", "#evidence", "#itsm"):
                    p.keyboard.press("Tab")
                    self.assertEqual(p.evaluate("document.activeElement.getAttribute('href')"), expected)
                    self.assertTrue(p.evaluate("document.activeElement.matches(':focus-visible') && getComputedStyle(document.activeElement).outlineStyle !== 'none' && parseFloat(getComputedStyle(document.activeElement).outlineWidth) >= 3"), f"Navigation focus indicator absent for {expected} at {width}px")
                for control in ("run-choice", "admission", "policy"):
                    p.keyboard.press("Tab")
                    self.assertEqual(p.evaluate("document.activeElement.id"), control,
                                     f"Tab order did not reach {control} at {width}px")
                    self.assertTrue(p.evaluate(
                        "document.activeElement.matches(':focus-visible') && getComputedStyle(document.activeElement).outlineStyle !== 'none' && parseFloat(getComputedStyle(document.activeElement).outlineWidth) >= 3"
                    ), f"Keyboard focus indicator absent for {control} at {width}px")
        self.assertEqual(self.allowed, [("GET", self.url)] * 4)
        self.assertEqual(self.requests, [("GET", self.url)] * 4)
        self.assertEqual(self.blocked, [], "Keyboard navigation attempted an unexpected request")
        self.assertFalse(self.errors)
    def test_viewports_and_states(self):
        p = self.page
        for width in (320, 1280, 1440, 1920):
            with self.subTest(width=width):
                p.set_viewport_size({"width": width, "height": 900})
                self.assertTrue(p.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Horizontal overflow at {width}px")
                for section in ("#incident", "#run", "#evidence", "#itsm"):
                    bounds = p.locator(section).bounding_box()
                    self.assertIsNotNone(bounds, f"{section} missing at {width}px")
                    self.assertGreaterEqual(bounds["x"], -1, f"{section} left-clipped at {width}px")
                    self.assertLessEqual(bounds["x"] + bounds["width"], width + 1, f"{section} right-clipped at {width}px")
                self.assertTrue(p.locator("#itsm").is_visible())
                for token in ("DEMO", "UNBOUND", "UNKNOWN", "MISSING", "NOT_RUN"):
                    self.assertIn(token, p.locator("body").inner_text())
                self.assertIn("Runtime attested: false", p.locator("#evidence").inner_text())
        self.assertEqual(self.allowed, [("GET", self.url)])
        self.assertEqual(self.requests, [("GET", self.url)])
        self.assertEqual(self.blocked, [], "Responsive flow attempted an unexpected request")
        self.assertFalse(self.errors, "Responsive flow raised a JavaScript error")
if __name__ == "__main__":
    unittest.main(verbosity=2)
