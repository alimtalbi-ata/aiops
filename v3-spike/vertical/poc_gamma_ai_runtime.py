"""Actual Chromium, actual local HTTP, synthetic provider and history fixtures."""
import tempfile,threading
from unittest.mock import patch
from playwright.sync_api import sync_playwright,expect
from ai_invocation_ledger import InvocationLedger
from poc_real_rag import seed
from test_rag_model_advisory import provider
from test_enterprise_context import graph
from http_demo import server

def exercise(http,history,ar,cr):
    t=threading.Thread(target=http.serve_forever,daemon=True);t.start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page()
                page.goto("http://127.0.0.1:%d"%http.server_port)
                button=page.locator("#ai-runtime-review")
                expect(button).to_be_enabled(timeout=10000)
                assert ar==[] and cr==[]
                page.locator("#assessment-runs").fill(" ".join(history["run_ids"]))
                button.click()
                result=page.locator("#ai-runtime-result")
                for value in ("Persisted receipt verified","RCA UNKNOWN","Policy DENY","APPLICABLE_CHECK"):
                    expect(result).to_contain_text(value,timeout=10000)
                assert len(ar)==len(cr)==1
                page.locator("#ai-runtime-measures").click()
                expect(page.locator("#ai-telemetry-result")).to_contain_text("Invocations: 2",timeout=10000)
                assert len(ar)==len(cr)==1
                held=[]
                def hold(route):held.append((route,route.fetch()))
                page.route("**/api/v1/enterprise-correlation/ai-review",hold)
                button.click()
                for _ in range(50):
                    if held:break
                    page.wait_for_timeout(100)
                assert len(held)==1
                page.locator("#assessment-window").fill("60")
                held[0][0].fulfill(response=held[0][1])
                page.unroute("**/api/v1/enterprise-correlation/ai-review",hold)
                expect(button).to_be_enabled(timeout=10000)
                expect(result).to_be_empty()
                expect(page.locator("#ai-runtime-measures")).to_be_disabled()
                assert len(ar)==len(cr)==2
                print("E27 GAMMA actual browser explicit review persisted receipt telemetry and stale response PASS")
            finally:browser.close()
    finally:http.shutdown();t.join(5)

with tempfile.TemporaryDirectory() as root:
    ledger=InvocationLedger(root)
    history,_=seed(ledger)
    g=graph()
    raw={"nodes":list(g.nodes.values()),"edges":[{"source_id":x,"target_id":y,"relation_type":z} for x,y,z in g.edges]}
    with provider("fixture-a","ANALYST") as (a,ar),provider("fixture-c","CRITIC") as (c,cr):
        with server(core_config=(18001,"synthetic-token","unused"),context_config=(18101,18102,"NODE-CI-ROOT","INC-CI-CONTEXT"),
                    enterprise_clock=ledger.clock,ai_providers={"analyst":a,"critic":c}) as http,patch("http_demo.get",return_value=raw),patch("enterprise_historical_correlation.historical_preview",return_value=history):
            exercise(http,history,ar,cr)
