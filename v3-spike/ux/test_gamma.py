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
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/index.html"
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()
    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
    def setUp(self):
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.requests = []
        self.errors = []
        self.page.on("request", lambda r: self.requests.append((r.method, r.url)))
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.route("**/*", lambda r: r.continue_() if r.request.url == self.url else r.abort())
        self.page.goto(self.url)
    def test_run_selection_and_refusal(self):
        p = self.page
        self.assertIn("STORAGE", p.locator("#run-result").inner_text())
        p.locator("#policy").click()
        self.assertIn("DENIED", p.locator("#decision").inner_text())
        p.locator("#run-choice").select_option("network")
        self.assertIn("NETWORK", p.locator("#run-result").inner_text())
        self.assertEqual(p.locator("#decision").inner_text(), "No action requested.")
        self.assertEqual(self.requests, [("GET", self.url)])
        self.assertFalse(self.errors)
    def test_keyboard(self):
        p = self.page
        for target in ["#incident", "#run", "#evidence", "#itsm"]:
            p.keyboard.press("Tab")
            self.assertEqual(p.evaluate("document.activeElement.getAttribute('href')"), target)
        p.keyboard.press("Enter")
        self.assertTrue(p.url.endswith("#itsm"))
        p.keyboard.press("Tab")
        # Anchor navigation can reposition sequential focus; explicitly test native select keyboard behavior.
        p.locator("#run-choice").focus()
        p.keyboard.press("ArrowDown")
        self.assertIn("NETWORK", p.locator("#run-result").inner_text())
        p.locator("#policy").focus()
        p.keyboard.press("Enter")
        self.assertIn("DENIED", p.locator("#decision").inner_text())
    def test_viewports_and_states(self):
        p = self.page
        for width in (320, 1280, 1440, 1920):
            with self.subTest(width=width):
                p.set_viewport_size({"width": width, "height": 900})
                self.assertTrue(p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
                self.assertTrue(p.locator("#itsm").is_visible())
                for token in ("DEMO", "UNBOUND", "UNKNOWN", "MISSING", "NOT_RUN"):
                    self.assertIn(token, p.locator("body").inner_text())
                self.assertIn("Runtime attested: false", p.locator("#evidence").inner_text())
if __name__ == "__main__":
    unittest.main(verbosity=2)
