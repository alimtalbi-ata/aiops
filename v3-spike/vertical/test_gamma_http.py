import threading
import unittest
from unittest.mock import patch
from http_demo import server

class GammaHttpTests(unittest.TestCase):
    def test_walkthrough_keyboard_focus(self):
        from playwright.sync_api import sync_playwright, expect
        targets = ["dynamic-ingestion", "enterprise-workbench",
                   "incident-context", "enterprise-inventory",
                   "dynamic-ingestion", "e17-recovery"]
        with server() as http:
            worker = threading.Thread(target=http.serve_forever, daemon=True)
            worker.start()
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True)
                    try:
                        for width in (390, 1280):
                            with self.subTest(width=width):
                                page = browser.new_page(viewport={"width": width, "height": 800})
                                try:
                                    page.goto("http://127.0.0.1:%d/" % http.server_port)
                                    links = page.get_by_role("navigation", name="Mono-incident demonstration").get_by_role("link")
                                    expect(links).to_have_count(len(targets))
                                    for index, target in enumerate(targets):
                                        link = links.nth(index)
                                        expect(link).to_have_attribute("href", "#" + target)
                                        link.focus()
                                        expect(link).to_be_focused()
                                        page.keyboard.press("Enter")
                                        expect(page.locator("#" + target)).to_be_focused()
                                        expect(page.locator("#dynamic-hitl-approve")).to_be_disabled()
                                        expect(page.locator("#hitl-approve")).to_be_disabled()
                                finally:
                                    page.close()
                    finally:
                        browser.close()
            finally:
                http.shutdown()
                worker.join(5)

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
                        # Exercise the actual browser-to-HTTP dynamic path with mocked services.
                        run_id="RUN-"+"A"*16
                        incident_id="INC-CI-INGEST-"+"a"*32
                        core={**projection,"run":{"run_id":run_id,"incident_id":incident_id,"mode":"DEMO","status":"CREATED"}}
                        evidence=[{"evidence_id":"E1","payload_hash":"a"*64},{"evidence_id":"E2","payload_hash":"b"*64}]
                        details={"classification":"SYNTHETIC_LAB_CONTEXT","run_id":run_id,"production_authorized":False,
                                 "tenant_acl_qualified":False,"policy":"DENY","rca":"UNKNOWN",
                                 "affected":[{"node_id":"NODE-CI-ROOT","depth":0}],"evidence":evidence}
                        http.context_config=(1814,1815,"NODE-CI-ROOT","INC-CI-FIXTURE")
                        with patch("http_demo.create_and_persist",return_value={"core":core,"stored_evidence":evidence,"production_authorized":False}) as create:
                            page.locator("#create-dynamic").click()
                            expect(page.locator("#dynamic-result")).to_contain_text(run_id)
                            self.assertEqual(create.call_args.args[0][0]["resource"],"NODE-CI-ROOT")
                            self.assertEqual(create.call_args.args[0][1]["observation"]["value"],160)
                        with patch("http_demo.dynamic_context",return_value=(core,details)) as read:
                            page.locator("#load-dynamic-context").click()
                            expect(page.locator("#context-result")).to_contain_text("Verified dynamic lab binding")
                            expect(page.locator("#context-result")).to_contain_text("Critic evidence: SUPPORTED")
                            self.assertEqual(read.call_args.args[2],run_id)
                        # Tamper only the browser response: duplicate one citation, omit the other.
                        def duplicate_citation(route):
                            response = route.fetch()
                            payload = response.json()
                            sources = payload["copilot"]["sources"]
                            self.assertEqual(len(sources), 2)
                            payload["copilot"]["sources"] = [sources[0], sources[0]]
                            route.fulfill(response=response, json=payload)
                        pattern = "**/api/v1/incident-context/dynamic?*"
                        page.route(pattern, duplicate_citation)
                        try:
                            with patch("http_demo.dynamic_context",return_value=(core,details)):
                                page.locator("#load-dynamic-context").click()
                                expect(page.locator("#context-result")).to_have_text("UNKNOWN / DENY — context unavailable or unverified")
                        finally:
                            page.unroute(pattern, duplicate_citation)
                        with patch("http_demo.dynamic_context",return_value=({**core,"run":{**core["run"],"run_id":"RUN-"+"B"*16}},dict(details,run_id="RUN-"+"B"*16))):
                            page.locator("#load-dynamic-context").click()
                            expect(page.locator("#context-result")).to_contain_text("UNKNOWN / DENY")
                        page.locator("#clear").click()
                        expect(page.locator("#load-dynamic-context")).to_be_disabled()
                        expect(page.locator("#dynamic-result")).to_have_text("UNKNOWN / DENY")
                        page.locator("#http-sim").click()
                        expect(page.locator("#policy-value")).to_contain_text("SIMULATE_ONLY")
                        page.locator("#eligibility").click()
                        expect(page.locator("#decision")).to_contain_text("DENIED")
                    finally:
                        browser.close()
            finally:
                http.shutdown()
                worker.join(5)
