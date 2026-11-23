"""Offline Chromium acceptance of C V0 synthetic projection; no network/host actions."""
import hashlib
import json
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

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
    def test_local_json_file_import_and_rejection(self):
        payload=json.dumps(fixture(True)).encode("utf-8")
        self.page.locator("#projection-file").set_input_files(
            {"name":"synthetic.json","mimeType":"application/json","buffer":payload})
        expect(self.page.locator("#file-status")).to_contain_text("No upload")
        self.assertIn("synthetic-001",self.page.locator("#payload").input_value())
        self.assertIn("UNKNOWN",self.page.locator("#state").inner_text())
        self.page.locator("#load").click()
        self.assertIn("SIMULATE_ONLY",self.page.locator("#policy-value").inner_text())
        self.page.locator("#projection-file").set_input_files(
            {"name":"oversized.json","mimeType":"application/json","buffer":b"x"*1048577})
        expect(self.page.locator("#file-status")).to_contain_text("REJECTED")
        self.assertEqual("",self.page.locator("#payload").input_value())
        self.assertIn("UNKNOWN",self.page.locator("#incident-value").inner_text())
        self.page.locator("#eligibility").click()
        self.assertIn("DENIED",self.page.locator("#decision").inner_text())
        self.page.locator("#clear").click()
        self.assertEqual("",self.page.locator("#projection-file").input_value())

    def test_pending_file_read_cannot_restore_cleared_projection(self):
        self.page.evaluate("""() => {
          window.pendingFileText = {};
          File.prototype.text = function() {
            return new Promise(resolve => { window.pendingFileText.resolve = resolve; });
          };
        }""")
        self.page.locator("#projection-file").set_input_files(
            {"name":"delayed.json","mimeType":"application/json","buffer":b"{}"})
        self.page.wait_for_function("typeof window.pendingFileText.resolve === 'function'")
        self.page.locator("#clear").click()
        self.page.evaluate("(text) => window.pendingFileText.resolve(text)", json.dumps(fixture(True)))
        self.page.wait_for_timeout(100)
        self.assertEqual("", self.page.locator("#payload").input_value())
        self.assertIn("UNKNOWN", self.page.locator("#state").inner_text())
        self.assertIn("DENIED", self.page.locator("#decision").inner_text())

    def test_pending_file_read_cannot_overwrite_manual_editor_changes(self):
        self.page.evaluate("""() => {
          window.pendingFileText = {};
          File.prototype.text = function() {
            return new Promise(resolve => { window.pendingFileText.resolve = resolve; });
          };
        }""")
        self.page.locator("#projection-file").set_input_files(
            {"name":"delayed.json","mimeType":"application/json","buffer":b"{}"})
        self.page.wait_for_function("typeof window.pendingFileText.resolve === 'function'")
        self.page.locator("#payload").fill(json.dumps(fixture()))
        self.page.evaluate("(text) => window.pendingFileText.resolve(text)", json.dumps(fixture(True)))
        self.page.wait_for_timeout(100)
        self.assertEqual(json.loads(self.page.locator("#payload").input_value())["policy"]["decision"], "DENY")
        self.assertIn("UNKNOWN / DENY", self.page.locator("#state").inner_text())
        self.page.locator("#eligibility").click()
        self.assertIn("DENIED", self.page.locator("#decision").inner_text())

    def test_pending_file_read_cannot_overwrite_explicit_inspection(self):
        self.page.evaluate("""() => {
          window.pendingFileText = {};
          File.prototype.text = function() {
            return new Promise(resolve => { window.pendingFileText.resolve = resolve; });
          };
        }""")
        self.page.locator("#projection-file").set_input_files(
            {"name":"delayed.json","mimeType":"application/json","buffer":b"{}"})
        self.page.wait_for_function("typeof window.pendingFileText.resolve === 'function'")
        self.page.locator("#payload").fill(json.dumps(fixture()))
        self.page.locator("#load").click()
        self.assertIn("DEMO", self.page.locator("#state").inner_text())
        self.assertIn("blocked", self.page.locator("#run-value").inner_text())
        self.page.evaluate("(text) => window.pendingFileText.resolve(text)", json.dumps(fixture(True)))
        self.page.wait_for_timeout(100)
        self.assertEqual(json.loads(self.page.locator("#payload").input_value())["policy"]["decision"], "DENY")
        self.assertIn("blocked", self.page.locator("#run-value").inner_text())
        self.page.locator("#eligibility").click()
        self.assertIn("DENIED", self.page.locator("#decision").inner_text())

    def test_pasted_size_and_control_character_rejected(self):
        self.load(fixture())
        self.assertIn("DEMO", self.page.locator("#state").inner_text())
        self.page.locator("#payload").fill(" " * 1048577)
        self.page.locator("#load").click()
        self.assertIn("UNKNOWN / DENY", self.page.locator("#state").inner_text())
        self.assertIn("NOT_RUN", self.page.locator("#run-value").inner_text())
        f=fixture()
        f["event"]["id"]="bad\ncontrol"
        self.load(f)
        self.assertIn("UNKNOWN / DENY", self.page.locator("#state").inner_text())
        self.page.locator("#eligibility").click()
        self.assertIn("DENIED", self.page.locator("#decision").inner_text())

    def test_bidi_and_c1_identifiers_fail_closed(self):
        for bad_id in ("visual\u202eexe", "direction\u2066isolate", "hidden\u0085control", "mark\u200frtl", "zero\u200bwidth", "join\u2060word", "bom\ufeffhidden", "surrogate\ud800bad", "soft\u00adhyphen", "arabic\u061cmark", "mongolian\u180eseparator", "grapheme\u034fjoiner", "line\u2028separator", "paragraph\u2029separator", "nbsp\u00a0separator", "figure\u2007space", "narrow\u202fspace", "ideographic\u3000space"):
            self.assertTrue(any(ord(ch) in (0x202e, 0x2066, 0x0085, 0x200f, 0x200b, 0x2060, 0xfeff, 0xd800, 0x00ad, 0x061c, 0x180e, 0x034f, 0x2028, 0x2029, 0x00a0, 0x2007, 0x202f, 0x3000) for ch in bad_id))
            f=fixture()
            f["event"]["id"]=bad_id
            self.load(f)
            self.assertIn("UNKNOWN / DENY",self.page.locator("#state").inner_text())
            self.assertIn("NOT_RUN",self.page.locator("#run-value").inner_text())
            self.page.locator("#eligibility").click()
            self.assertIn("DENIED",self.page.locator("#decision").inner_text())

    def test_non_object_json_roots_fail_closed_after_valid_inspection(self):
        self.load(fixture())
        self.assertIn("DEMO", self.page.locator("#state").inner_text())
        for raw in ("null", "[]", "42", "true", '"synthetic"'):
            self.page.locator("#payload").fill(raw)
            self.page.locator("#load").click()
            self.assertIn("UNKNOWN / DENY", self.page.locator("#state").inner_text())
            self.assertIn("NOT_RUN", self.page.locator("#run-value").inner_text())
            self.page.locator("#eligibility").click()
            self.assertIn("DENIED", self.page.locator("#decision").inner_text())

    def test_multibyte_pasted_projection_uses_utf8_byte_limit(self):
        # Character count is below 1 MiB, but UTF-8 bytes exceed the limit.
        f=fixture()
        f["synthetic_padding"]="é"*524288
        payload=json.dumps(f,ensure_ascii=False)
        self.assertLess(len(payload),1048576)
        self.assertGreater(len(payload.encode("utf-8")),1048576)
        self.page.locator("#payload").fill(payload)
        self.page.locator("#load").click()
        self.assertIn("UNKNOWN / DENY",self.page.locator("#state").inner_text())
        self.assertIn("NOT_RUN",self.page.locator("#run-value").inner_text())
        self.page.locator("#eligibility").click()
        self.assertIn("DENIED",self.page.locator("#decision").inner_text())

    def test_untrusted_identifiers_render_as_text_not_markup(self):
        f=fixture()
        f["event"]["id"]="<img src=x onerror=alert(1)>"
        f["event"]["source"]="<svg onload=alert(2)>"
        f["event"]["resource"]="<script>alert(3)</script>"
        f["incident"]["id"]="<b>synthetic-incident</b>"
        f["twin"]["resource"]=f["event"]["resource"]
        f["twin"]["evidence"]["source"]=f["event"]["source"]
        f["receipt"]["incident_id"]=f["incident"]["id"]
        f["gamma"]["incident"]=f["incident"]
        f["gamma"]["twin"]=f["twin"]
        f["gamma"]["receipt"]=f["receipt"]
        self.load(f)
        self.assertIn("DEMO",self.page.locator("#state").inner_text())
        self.assertIn("<img",self.page.locator("#incident-value").inner_text())
        self.assertIn("<script>",self.page.locator("#twin-value").inner_text())
        self.assertEqual(self.page.locator("#incident-value img, #incident-value svg, #twin-value script, #incident-value b").count(),0)
        self.page.locator("#eligibility").click()
        self.assertIn("DENIED",self.page.locator("#decision").inner_text())

    def test_keyboard_and_viewports(self):
        links=["#input","#incident","#twin","#policy","#receipt"]
        self.assertEqual(self.page.locator('nav[aria-label="Vertical sections"] a').count(),len(links))
        for width in (320,1280,1920):
            self.page.set_viewport_size({"width":width,"height":900})
            self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            self.page.set_content(HTML.read_text(encoding="utf-8"),wait_until="load")
            self.page.keyboard.press("Tab")
            for target in links:
                self.assertEqual(self.page.evaluate('document.activeElement.getAttribute("href")'),target)
                self.assertTrue(self.page.evaluate('document.activeElement.matches(":focus-visible")'))
                self.page.keyboard.press("Enter")
                self.assertEqual(self.page.evaluate("location.hash"),target)
                self.assertIn("DENIED",self.page.locator("#decision").inner_text())
                self.page.keyboard.press("Tab")
            self.assertEqual(self.page.evaluate("document.activeElement.id"),"section-select")
            self.assertTrue(self.page.evaluate('document.activeElement.matches(":focus-visible")'))
            for target in links:
                self.page.locator("#section-select").select_option(target[1:])
                self.assertEqual(self.page.evaluate("location.hash"),target)
                self.assertEqual(self.page.evaluate("document.activeElement.id"),target[1:])
                self.assertIn("DENIED",self.page.locator("#decision").inner_text())
                self.page.locator("#section-select").focus()
            self.page.keyboard.press("Tab")
            self.assertEqual(self.page.evaluate("document.activeElement.id"),"projection-file")
            self.assertTrue(self.page.evaluate('document.activeElement.matches(":focus-visible")'))
            self.page.keyboard.press("Tab")
            self.assertEqual(self.page.evaluate("document.activeElement.id"),"payload")
            self.page.keyboard.press("Tab")
            self.assertEqual(self.page.evaluate("document.activeElement.id"),"load")
            self.assertTrue(self.page.evaluate('document.activeElement.matches(":focus-visible")'))

    def test_second_file_selection_supersedes_first_pending_read(self):
        self.page.evaluate("""() => {
          window.pendingFiles = [];
          File.prototype.text = function() {
            return new Promise(resolve => window.pendingFiles.push(resolve));
          };
        }""")
        picker=self.page.locator("#projection-file")
        picker.set_input_files({"name":"first.json","mimeType":"application/json","buffer":b"{}"})
        self.page.wait_for_function("window.pendingFiles.length === 1")
        picker.set_input_files({"name":"second.json","mimeType":"application/json","buffer":b"{ }"})
        self.page.wait_for_function("window.pendingFiles.length === 2")
        self.page.evaluate("(text) => window.pendingFiles[1](text)", json.dumps(fixture()))
        expect(self.page.locator("#payload")).to_have_value(json.dumps(fixture()))
        self.page.evaluate("(text) => window.pendingFiles[0](text)", json.dumps(fixture(True)))
        self.page.wait_for_timeout(100)
        self.assertEqual(json.loads(self.page.locator("#payload").input_value())["policy"]["decision"],"DENY")
        self.assertIn("UNKNOWN",self.page.locator("#state").inner_text())
        self.page.locator("#load").click()
        self.assertIn("blocked",self.page.locator("#run-value").inner_text())
        self.page.locator("#eligibility").click()
        self.assertIn("DENIED",self.page.locator("#decision").inner_text())

    def test_stale_file_read_rejection_cannot_erase_manual_projection(self):
        self.page.evaluate("""() => {
          window.pendingReject = {};
          File.prototype.text = function() {
            return new Promise((resolve, reject) => { window.pendingReject.reject = reject; });
          };
        }""")
        self.page.locator("#projection-file").set_input_files(
            {"name":"delayed.json","mimeType":"application/json","buffer":b"{}"})
        self.page.wait_for_function("typeof window.pendingReject.reject === 'function'")
        self.page.locator("#payload").fill(json.dumps(fixture()))
        self.page.locator("#load").click()
        self.assertIn("DEMO", self.page.locator("#state").inner_text())
        self.page.evaluate("() => window.pendingReject.reject(new Error('synthetic read failure'))")
        self.page.wait_for_timeout(100)
        self.assertEqual(json.loads(self.page.locator("#payload").input_value())["policy"]["decision"], "DENY")
        self.assertIn("DEMO", self.page.locator("#state").inner_text())
        self.assertIn("blocked", self.page.locator("#run-value").inner_text())
        self.assertIn("DENIED", self.page.locator("#decision").inner_text())

if __name__=="__main__": unittest.main(verbosity=2)
