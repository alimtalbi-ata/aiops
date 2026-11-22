"""Offline Chromium acceptance of C V0 synthetic projection; no network/host actions."""
import hashlib
import json
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML = Path(__file__).with_name("vertical_operator.html")
def canonical(x): return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def fixture(approved=False):
    e={"id":"synthetic-001","source":"synthetic-monitor","severity":"critical","resource":"demo-node-01"}
    h=hashlib.sha256(canonical(e).encode()).hexdigest()
    i={"id":"inc-"+hashlib.sha256(e["id"].encode()).hexdigest()[:12],"severity":"critical","status":"open"}
    t={"resource":e["resource"],"correlation":"same-resource","evidence":{"event_sha256":h,"source":e["source"]}}
    p={"decision":"SIMULATE_ONLY" if approved else "DENY","hitl":"approved_synthetic" if approved else "required"}
    r={"mode":"SIMULATED","executed_on_host":False,"status":"simulated" if approved else "blocked"}
    c={"incident_id":i["id"],"policy":p["decision"],"run_status":r["status"],"evidence_sha256":h}
    c["sha256"]=hashlib.sha256(canonical(c).encode()).hexdigest()
    return {"event":e,"incident":i,"twin":t,"policy":p,"run":r,"receipt":c,"gamma":{"view":"incident","incident":i,"twin":t,"policy":p,"run":r,"receipt":c},"production_authorized":False}

class VerticalOperator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch()
    @classmethod
    def tearDownClass(cls): cls.browser.close();cls.pw.stop()
    def setUp(self):
        self.page=self.browser.new_page();self.requests=[];self.errors=[]
        self.page.on("request",lambda req:self.requests.append(req.url))
        self.page.on("pageerror",lambda err:self.errors.append(str(err)))
        self.page.route("**/*",lambda route:route.abort())
        self.page.set_content(HTML.read_text(encoding="utf-8"),wait_until="load")
    def tearDown(self):
        self.assertEqual(self.requests,[]);self.assertEqual(self.errors,[]);self.page.close()
    def load(self,payload):
        self.page.locator("#payload").fill(json.dumps(payload));self.page.locator("#load").click()
    def test_denied_projection(self):
        self.load(fixture());self.assertIn("DEMO",self.page.locator("#state").inner_text())
        self.assertIn("blocked",self.page.locator("#run-value").inner_text())
        self.page.locator("#eligibility").click();self.assertIn("DENIED",self.page.locator("#decision").inner_text())
    def test_simulated_projection_never_allows(self):
        self.load(fixture(True));self.assertIn("SIMULATE_ONLY",self.page.locator("#policy-value").inner_text())
        self.assertIn("simulated",self.page.locator("#run-value").inner_text())
        self.page.locator("#eligibility").click();self.assertIn("DENIED",self.page.locator("#decision").inner_text())
    def test_tamper_fails_closed(self):
        for key,value in [("production_authorized",True),("receipt",{"sha256":"bad"}),("gamma",{"view":"incident"}),("run",{"executed_on_host":True})]:
            f=fixture();f[key]=value;self.load(f)
            self.assertIn("UNKNOWN / DENY",self.page.locator("#state").inner_text())
            self.assertIn("NOT_RUN",self.page.locator("#run-value").inner_text())
    def test_empty_invalid_reset(self):
        self.load(fixture());self.page.locator("#payload").fill("{");self.page.locator("#load").click()
        self.assertIn("UNKNOWN / DENY",self.page.locator("#state").inner_text())
        self.assertIn("UNKNOWN",self.page.locator("#incident-value").inner_text())
        self.page.locator("#clear").click();self.assertEqual(self.page.locator("#payload").input_value(),"")
    def test_keyboard_and_viewports(self):
        for width in (320,1280,1920):
            self.page.set_viewport_size({"width":width,"height":900})
            self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        self.page.keyboard.press("Tab")
        self.assertEqual(self.page.evaluate('document.activeElement.getAttribute("href")'),"#input")
        self.assertTrue(self.page.evaluate('document.activeElement.matches(":focus-visible")'))

if __name__=="__main__": unittest.main(verbosity=2)
