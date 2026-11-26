"""Actual Chromium + loopback HTTP + persistent synthetic fixture ledger."""
import tempfile,threading
from playwright.sync_api import sync_playwright,expect
from ai_invocation_ledger import InvocationLedger
from test_gamma_ai_telemetry import fixture
from http_demo import server

with tempfile.TemporaryDirectory() as root:
    ledger=InvocationLedger(root)
    ids,review=fixture(ledger)
    with server(enterprise_clock=ledger.clock) as http:
        t=threading.Thread(target=http.serve_forever,daemon=True);t.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True)
                try:
                    page=browser.new_page()
                    page.goto("http://127.0.0.1:%d"%http.server_port)
                    page.locator("#ai-telemetry-runs").fill(" ".join(ids))
                    page.locator("#ai-telemetry-read").click()
                    result=page.locator("#ai-telemetry-result")
                    for text in (review,"Invocations: 2","Tokens IN 10","Total 15","Total unavailable","Cost unavailable","Policy DENY"):
                        expect(result).to_contain_text(text,timeout=10000)
                    held=[]
                    def hold(route):held.append((route,route.fetch()))
                    page.route("**/api/v1/ai-telemetry",hold)
                    page.locator("#ai-telemetry-read").click()
                    for _ in range(50):
                        if held:break
                        page.wait_for_timeout(100)
                    assert len(held)==1
                    page.locator("#ai-telemetry-runs").fill(ids[0])
                    held[0][0].fulfill(response=held[0][1])
                    page.unroute("**/api/v1/ai-telemetry",hold)
                    page.wait_for_timeout(250)
                    expect(result).to_be_empty()
                    page.locator("#ai-telemetry-read").click()
                    expect(page.locator("#ai-telemetry-state")).to_have_text("NO_RECEIPTS / DENY")
                    print("E26 GAMMA actual browser persisted synthetic telemetry scope and stale response PASS")
                finally:browser.close()
        finally:http.shutdown();t.join(5)
