import threading
import unittest
from unittest.mock import patch
from http_demo import server

class GammaHttpTests(unittest.TestCase):
    def test_connected_gamma(self):
        from playwright.sync_api import sync_playwright, expect
        with server() as http:
            worker = threading.Thread(target=http.serve_forever, daemon=True)
            worker.start()
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True)
                    try:
                        page = browser.new_page()
                        page.goto("http://127.0.0.1:%d/" % http.server_port)
                        page.locator("#load-core").click()
                        expect(page.locator("#core-result")).to_contain_text("UNKNOWN / DENY")
                        http.core_config=(1810,"x"*32,"RUN-01")
                        projection={"classification":"SYNTHETIC_CANONICAL_RUN","production_authorized":False,
                                    "tenant_acl_qualified":False,"policy":"DENY","rca":"UNKNOWN",
                                    "run":{"run_id":"RUN-01","incident_id":"INC-01","mode":"DEMO","status":"CREATED"}}
                        with patch("http_demo.read_run",return_value=projection):
                            page.locator("#load-core").click()
                            expect(page.locator("#core-result")).to_contain_text("INC-01")
                            expect(page.locator("#core-result")).to_contain_text("Policy: DENY")
                        page.locator("#clear").click()
                        expect(page.locator("#core-result")).to_contain_text("not loaded")
                        page.locator("#load-incidents").click()
                        expect(page.locator("#correlated-result")).to_contain_text("2 alerts")
                        expect(page.locator("#correlated-result")).to_contain_text("synthetic-002")
                        expect(page.locator("#correlated-result")).to_contain_text("RCA: UNKNOWN")
                        page.locator("#http-sim").click()
                        expect(page.locator("#policy-value")).to_contain_text("SIMULATE_ONLY")
                        page.locator("#eligibility").click()
                        expect(page.locator("#decision")).to_contain_text("DENIED")
                    finally:
                        browser.close()
            finally:
                http.shutdown()
                worker.join(5)
