"""Real C CLI -> reviewed A GAMMA browser E2E, synthetic-only, no host actions."""
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
HTML = ROOT / "operator.html"
CLI = ROOT / "vertical_demo.py"


def cli_receipt(*args):
    result = subprocess.run(
        [sys.executable, "-B", str(CLI), *args],
        check=True, capture_output=True, text=True, timeout=15,
    )
    return json.loads(result.stdout)


class VerticalOperatorE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.requests = []
        self.page.on("request", lambda req: self.requests.append(req.url))
        self.page.goto(HTML.as_uri())

    def tearDown(self):
        self.page.close()

    def inspect(self, payload):
        self.page.locator("#payload").fill(json.dumps(payload))
        self.page.locator("#load").click()
        self.page.locator("#eligibility").click()

    def assert_safe(self):
        self.assertIn("DENIED", self.page.locator("#decision").inner_text())
        self.assertEqual(self.requests, [])

    def test_real_cli_denied_to_gamma(self):
        receipt = cli_receipt()
        self.assertEqual(receipt["policy"]["decision"], "DENY")
        self.inspect(receipt)
        self.assertIn("DEMO", self.page.locator("#state").inner_text())
        self.assertIn("DENY", self.page.locator("#policy-value").inner_text())
        self.assertIn(receipt["receipt"]["sha256"], self.page.locator("#receipt-value").inner_text())
        self.assert_safe()

    def test_real_cli_simulate_only_to_gamma(self):
        receipt = cli_receipt("--approved-synthetic")
        self.assertEqual(receipt["policy"]["decision"], "SIMULATE_ONLY")
        self.assertIs(receipt["run"]["executed_on_host"], False)
        self.inspect(receipt)
        self.assertIn("SIMULATE_ONLY", self.page.locator("#policy-value").inner_text())
        self.assertIn("operational DENY", self.page.locator("#policy-value").inner_text())
        self.assert_safe()

    def test_tampered_cli_receipt_rejected(self):
        receipt = cli_receipt()
        receipt["gamma"]["receipt"]["sha256"] = "0" * 64
        self.inspect(receipt)
        self.assertIn("UNKNOWN / DENY", self.page.locator("#state").inner_text())
        self.assert_safe()

    def test_production_authorization_rejected(self):
        receipt = cli_receipt("--approved-synthetic")
        receipt["production_authorized"] = True
        self.inspect(receipt)
        self.assertIn("UNKNOWN / DENY", self.page.locator("#state").inner_text())
        self.assert_safe()


if __name__ == "__main__":
    unittest.main()
