"""Offline, exact-file Chromium acceptance (no HTTP server; synthetic only)."""
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML = Path(__file__).with_name("index.html")

class GammaOffline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()
    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
    def setUp(self):
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.requests, self.errors = [], []
        self.page.on("request", lambda request: self.requests.append(request.url))
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.route("**/*", lambda route: route.abort())
        self.page.set_content(HTML.read_text(encoding="utf-8"), wait_until="load")
    def tearDown(self):
        self.assertEqual(self.requests, [], "No network request is permitted")
        self.assertEqual(self.errors, [], "No JavaScript error is permitted")
    def test_keyboard_and_focus(self):
        p = self.page
        for href in ("#incident", "#run", "#evidence", "#itsm"):
            p.keyboard.press("Tab")
            self.assertEqual(p.evaluate("document.activeElement.getAttribute('href')"), href)
            self.assertTrue(p.evaluate("document.activeElement.matches(':focus-visible')"))
        for target in ("run-choice", "admission", "binding-case", "policy"):
            p.keyboard.press("Tab")
            self.assertEqual(p.evaluate("document.activeElement.id"), target)
            self.assertTrue(p.evaluate("document.activeElement.matches(':focus-visible')"))
        p.keyboard.press("Shift+Tab")
        self.assertEqual(p.evaluate("document.activeElement.id"), "binding-case")
        self.assertTrue(p.evaluate("document.activeElement.matches(':focus-visible')"))
        p.keyboard.press("Tab")
        self.assertEqual(p.evaluate("document.activeElement.id"), "policy")
        p.keyboard.press("Enter")
        self.assertIn("DENIED", p.locator("#decision").inner_text())
    def test_snapshot_fail_closed(self):
        p = self.page
        for scenario in ("unknown", "revision-mismatch", "unattested-snapshot", "twin-substituted", "evidence-substituted"):
            p.locator("#binding-case").select_option(scenario)
            self.assertIn("DENY", p.locator("#binding-result").inner_text())
            self.assertIn("UNKNOWN", p.locator("#snapshot-status").inner_text())
            p.locator("#policy").click()
            self.assertIn("DENIED", p.locator("#decision").inner_text())
    def test_demo_never_authorizes(self):
        p = self.page
        p.locator("#binding-case").select_option("matched")
        self.assertIn("ALLOW_SYNTHETIC", p.locator("#binding-result").inner_text())
        self.assertIn("UNKNOWN", p.locator("#snapshot-status").inner_text())
        p.locator("#policy").click()
        self.assertIn("DENIED", p.locator("#decision").inner_text())
    def test_adversarial_unknown_selection_denied(self):
        p = self.page
        # Unknown injected DOM value must fail closed, without network or JS errors.
        p.locator("#binding-case").evaluate("(el) => { el.add(new Option('Injected', 'unexpected')); el.value = 'unexpected'; el.dispatchEvent(new Event('change', {bubbles:true})); }")
        self.assertIn("DENY", p.locator("#binding-result").inner_text())
        self.assertIn("UNKNOWN", p.locator("#snapshot-status").inner_text())
        p.locator("#policy").click()
        self.assertIn("DENIED", p.locator("#decision").inner_text())
        # Recovery to the known synthetic match must still never authorize action.
        p.locator("#binding-case").select_option("matched")
        self.assertIn("ALLOW_SYNTHETIC", p.locator("#binding-result").inner_text())
        p.locator("#policy").click()
        self.assertIn("DENIED", p.locator("#decision").inner_text())
    def test_policy_reset_on_binding_change(self):
        p = self.page
        p.locator("#binding-case").select_option("matched")
        p.locator("#policy").click()
        self.assertIn("DENIED", p.locator("#decision").inner_text())
        p.locator("#binding-case").select_option("revision-mismatch")
        self.assertEqual(p.locator("#decision").inner_text(), "No action requested.")
        self.assertIn("DENY", p.locator("#binding-result").inner_text())
        self.assertIn("UNKNOWN", p.locator("#snapshot-status").inner_text())
        p.locator("#policy").click()
        self.assertIn("DENIED", p.locator("#decision").inner_text())
        p.locator("#binding-case").select_option("matched")
        self.assertEqual(p.locator("#decision").inner_text(), "No action requested.")
        self.assertIn("ALLOW_SYNTHETIC", p.locator("#binding-result").inner_text())
        self.assertIn("UNKNOWN", p.locator("#snapshot-status").inner_text())
        p.locator("#policy").click()
        self.assertIn("DENIED", p.locator("#decision").inner_text())
    def test_accessibility_semantics_and_adversarial_run(self):
        p = self.page
        self.assertEqual(p.locator('html').get_attribute('lang'), 'en')
        self.assertEqual(p.locator('nav[aria-label="Incident sections"] a').count(), 4)
        for control in ("run-choice", "admission", "binding-case"):
            self.assertEqual(p.locator(f'label[for="{control}"]').count(), 1)
            self.assertEqual(p.locator(f'#{control}').count(), 1)
        for status in ("run-result", "admission-result", "binding-result", "snapshot-status", "decision"):
            self.assertEqual(p.locator(f'#{status}').get_attribute("role"), "status")
        # Synthetic DOM tampering must not turn an unknown Run into a valid action.
        p.locator("#run-choice").evaluate(
            "(el) => { el.add(new Option('Injected', 'unexpected-run')); el.value = 'unexpected-run'; el.dispatchEvent(new Event('change', {bubbles:true})); }"
        )
        self.assertIn("UNKNOWN", p.locator("#run-result").inner_text())
        self.assertIn("NOT_RUN", p.locator("#run-result").inner_text())
        self.assertEqual(p.locator("#admission").input_value(), "unknown")
        p.locator("#policy").click()
        self.assertIn("DENIED", p.locator("#decision").inner_text())
        p.locator("#run-choice").select_option("storage")
        self.assertEqual(p.locator("#decision").inner_text(), "No action requested.")
        p.locator("#policy").click()
        self.assertIn("DENIED", p.locator("#decision").inner_text())
    def test_admission_states_never_attest_or_authorize(self):
        p = self.page
        # A synthetic admission receipt is not a verified Evidence or runtime attestation.
        for receipt, marker in (("accept", "ACCEPT"), ("duplicate", "DUPLICATE"), ("refused", "REFUSED"), ("unknown", "UNKNOWN")):
            p.locator("#admission").select_option(receipt)
            self.assertIn(marker, p.locator("#admission-result").inner_text())
            self.assertIn("UNKNOWN", p.locator("#snapshot-status").inner_text())
            self.assertEqual(p.locator("#decision").inner_text(), "No action requested.")
            p.locator("#policy").click()
            self.assertIn("DENIED", p.locator("#decision").inner_text())
            # Switching receipts must not retain a prior policy decision.
            p.locator("#binding-case").select_option("matched")
            p.locator("#binding-case").select_option("revision-mismatch")
            self.assertIn("DENY", p.locator("#binding-result").inner_text())
            self.assertEqual(p.locator("#decision").inner_text(), "No action requested.")
        p.locator("#binding-case").select_option("matched")
        self.assertIn("ALLOW_SYNTHETIC", p.locator("#binding-result").inner_text())
        p.locator("#policy").click()
        self.assertIn("DENIED", p.locator("#decision").inner_text())
    def test_viewports(self):
        p = self.page
        for width in (320, 1280, 1920):
            p.set_viewport_size({"width": width, "height": 900})
            self.assertTrue(p.evaluate("document.documentElement.scrollWidth <= innerWidth"), width)
            self.assertEqual(p.locator('nav[aria-label="Incident sections"] a').count(), 4)
            for href in ("#incident", "#run", "#evidence", "#itsm"):
                self.assertTrue(p.locator(href).is_visible())
    def test_run_change_invalidates_prior_binding_and_policy(self):
        p = self.page
        p.locator("#binding-case").select_option("matched")
        self.assertIn("ALLOW_SYNTHETIC", p.locator("#binding-result").inner_text())
        p.locator("#admission").select_option("accept")
        p.locator("#policy").click()
        self.assertIn("DENIED", p.locator("#decision").inner_text())
        p.locator("#run-choice").select_option("network")
        self.assertEqual(p.locator("#binding-case").input_value(), "unknown")
        self.assertIn("DENY", p.locator("#binding-result").inner_text())
        self.assertIn("UNKNOWN", p.locator("#snapshot-status").inner_text())
        self.assertEqual(p.locator("#admission").input_value(), "unknown")
        self.assertEqual(p.locator("#decision").inner_text(), "No action requested.")
        p.locator("#policy").click()
        self.assertIn("DENIED", p.locator("#decision").inner_text())
        p.locator("#run-choice").select_option("storage")
        self.assertEqual(p.locator("#binding-case").input_value(), "unknown")
        self.assertNotIn("ALLOW_SYNTHETIC", p.locator("#binding-result").inner_text())

    def test_receipt_change_invalidates_prior_binding(self):
        p = self.page
        p.locator("#binding-case").select_option("matched")
        self.assertIn("ALLOW_SYNTHETIC", p.locator("#binding-result").inner_text())
        p.locator("#policy").click()
        self.assertIn("DENIED", p.locator("#decision").inner_text())
        for receipt in ("accept", "duplicate", "refused", "unknown"):
            p.locator("#binding-case").select_option("matched")
            self.assertIn("ALLOW_SYNTHETIC", p.locator("#binding-result").inner_text())
            p.locator("#admission").select_option(receipt)
            self.assertEqual(p.locator("#binding-case").input_value(), "unknown")
            self.assertIn("DENY", p.locator("#binding-result").inner_text())
            self.assertIn("UNKNOWN", p.locator("#snapshot-status").inner_text())
            self.assertEqual(p.locator("#decision").inner_text(), "No action requested.")
            p.locator("#policy").click()
            self.assertIn("DENIED", p.locator("#decision").inner_text())

    def test_run_admission_reset(self):
        p = self.page
        p.locator("#admission").select_option("accept")
        self.assertIn("ACCEPT", p.locator("#admission-result").inner_text())
        p.locator("#run-choice").select_option("network")
        self.assertIn("NETWORK", p.locator("#run-result").inner_text())
        self.assertEqual(p.locator("#admission").input_value(), "unknown")
        self.assertIn("UNKNOWN", p.locator("#admission-result").inner_text())

if __name__ == "__main__":
    unittest.main(verbosity=2)
