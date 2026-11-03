"""Real Chromium on an ephemeral loopback portal. Synthetic UI only, never Debian."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.parse import urlsplit
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class DemoCenter386Chromium(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="aiops-democenter-ci-")
        cls.log = open(Path(cls.tmp.name) / "portal.log", "w+b")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        cls.base = "http://127.0.0.1:" + str(cls.port)
        env = os.environ.copy()
        env.update({
            "PYTHONPATH": str(ROOT / "app"),
            "AIOPS_INTERNAL_TOKEN": "ci-only-internal-ephemeral",
            "CORE_URL": "http://127.0.0.1:9",
            "TWIN_URL": "http://127.0.0.1:9",
            "COPILOT_URL": "http://127.0.0.1:9",
        })
        cls.server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "portal.main:app",
             "--host", "127.0.0.1", "--port", str(cls.port)],
            cwd=ROOT, env=env, stdout=cls.log, stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(80):
                if cls.server.poll() is not None:
                    raise RuntimeError("ephemeral portal exited")
                try:
                    with urlopen(cls.base + "/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                time.sleep(0.25)
            else:
                raise RuntimeError("ephemeral portal not ready")
            cls.pw = sync_playwright().start()
            cls.browser = cls.pw.chromium.launch(headless=True, args=["--no-sandbox"])
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "browser"):
            cls.browser.close()
        if hasattr(cls, "pw"):
            cls.pw.stop()
        if hasattr(cls, "server"):
            cls.server.terminate()
            try:
                cls.server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.server.kill()
                cls.server.wait(timeout=5)
        if hasattr(cls, "log"):
            cls.log.close()
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def setUp(self):
        self.context = self.browser.new_context(
            service_workers="block", accept_downloads=False,
            viewport={"width": 1280, "height": 900},
        )
        self.requests = []
        def fence(route):
            url = urlsplit(route.request.url)
            self.requests.append((route.request.method, route.request.url))
            if (url.scheme == "http" and url.hostname == "127.0.0.1"
                    and url.port == self.port and route.request.method == "GET"):
                route.continue_()
            else:
                route.abort()
        self.context.route("**/*", fence)
        self.page = self.context.new_page()

    def tearDown(self):
        self.context.close()

    def test_01_navigation_and_existing_synthetic_views(self):
        self.page.goto(self.base + "/")
        self.page.get_by_role("link", name="DemoCenter / Vidéo").click()
        expect(self.page).to_have_url(self.base + "/demo-center")
        expect(self.page.locator("#san-scenario option")).to_have_count(8)
        expect(self.page.locator("#scenario-status")).to_contain_text("NOT_ATTESTED")
        self.page.locator("#san-scenario").select_option("multipath")
        expect(self.page.locator("#scenario-status")).to_contain_text("non exécuté")
        self.page.get_by_role("link", name="Voir le graphe existant").click()
        expect(self.page).to_have_url(self.base + "/demo/acme-impact")
        expect(self.page.locator("body")).to_contain_text("SIM")
        self.page.goto(self.base + "/demo-center")
        self.page.get_by_role("link", name="Ouvrir Explore / Story").click()
        expect(self.page).to_have_url(self.base + "/demo/explore-story")
        self.assertTrue(all(method == "GET" for method, _ in self.requests))
        target = Path(os.environ.get("AIOPS_E2E_ARTIFACT_DIR", self.tmp.name))
        target.mkdir(parents=True, exist_ok=True)
        self.page.goto(self.base + "/demo-center")
        self.page.screenshot(path=str(target / "democenter-ci-synthetic.png"), full_page=True)

    def test_02_permission_refusal_does_not_claim_recording(self):
        self.page.add_init_script("""(() => {
          Object.defineProperty(navigator.mediaDevices, "getDisplayMedia", {
            configurable: true, value: async () => { throw new DOMException("Denied", "NotAllowedError"); }
          });
        })();""")
        self.page.goto(self.base + "/demo-center")
        expect(self.page.locator("#record-start")).to_be_disabled()
        self.page.locator("#recording-consent").check()
        expect(self.page.locator("#record-start")).to_be_enabled()
        self.page.locator("#record-start").click()
        expect(self.page.locator("#recording-status")).to_contain_text("DENIED_OR_UNAVAILABLE")
        self.assertTrue(self.page.locator("#record-download").is_hidden())
        self.assertTrue(all(method == "GET" for method, _ in self.requests))

    def test_03_local_recorder_start_stop_preview_export_mock_device(self):
        # Browser state test with an explicit mock device, NOT a real screen capture.
        self.page.add_init_script("""(() => {
          const track = { stop() {}, addEventListener() {} };
          Object.defineProperty(navigator.mediaDevices, "getDisplayMedia", {
            configurable: true,
            value: async () => ({getTracks: () => [track], getVideoTracks: () => [track]})
          });
          window.MediaRecorder = class {
            constructor() { this.state = "inactive"; this.mimeType = "video/webm"; this.handlers = {}; }
            static isTypeSupported(t) { return t === "video/webm"; }
            addEventListener(name, callback) { this.handlers[name] = callback; }
            start() { this.state = "recording"; }
            stop() {
              this.state = "inactive";
              this.handlers.dataavailable({data: new Blob(["ci-fake-video"], {type: "video/webm"})});
              this.handlers.stop();
            }
          };
        })();""")
        self.page.goto(self.base + "/demo-center")
        self.page.locator("#recording-consent").check()
        self.page.locator("#record-start").click()
        expect(self.page.locator("#recording-status")).to_contain_text("RECORDING_LOCAL")
        self.page.locator("#record-stop").click()
        expect(self.page.locator("#recording-status")).to_contain_text("LOCAL_ONLY")
        expect(self.page.locator("#record-download")).to_be_visible()
        self.assertTrue(self.page.locator("#record-download").get_attribute("href").startswith("blob:"))
        self.page.locator("#record-clear").click()
        expect(self.page.locator("#record-download")).to_be_hidden()
        expect(self.page.locator("#recording-status")).to_contain_text("CLEARED")
        self.assertTrue(all(method == "GET" for method, _ in self.requests))


    def test_04_clear_cancels_pending_permission_prompt(self):
        self.page.add_init_script("""(() => {
          window.__resolveDisplay = null;
          Object.defineProperty(navigator.mediaDevices, "getDisplayMedia", {
            configurable: true,
            value: () => new Promise(resolve => { window.__resolveDisplay = resolve; })
          });
        })();""")
        self.page.goto(self.base + "/demo-center")
        self.page.locator("#recording-consent").check()
        self.page.locator("#record-start").click()
        expect(self.page.locator("#recording-status")).to_contain_text("PERMISSION_PENDING")
        self.page.locator("#record-clear").click()
        self.page.evaluate("""() => {
          const track = {stop() {}};
          window.__resolveDisplay({getTracks: () => [track], getVideoTracks: () => [track]});
        }""")
        expect(self.page.locator("#recording-status")).to_contain_text("CLEARED")
        expect(self.page.locator("#record-download")).to_be_hidden()
        self.assertTrue(all(method == "GET" for method, _ in self.requests))


    def test_05_consent_withdrawal_discards_delayed_recorder_output(self):
        # A delayed MediaRecorder.stop event must not resurrect a secret-containing blob.
        self.page.add_init_script("""(() => {
          window.__stoppedTracks = 0;
          const track = {
            stop() { window.__stoppedTracks += 1; },
            addEventListener() {}
          };
          Object.defineProperty(navigator.mediaDevices, "getDisplayMedia", {
            configurable: true,
            value: async () => ({getTracks: () => [track], getVideoTracks: () => [track]})
          });
          window.MediaRecorder = class {
            constructor() { this.state = "inactive"; this.mimeType = "video/webm"; this.handlers = {}; }
            static isTypeSupported(t) { return t === "video/webm"; }
            addEventListener(name, callback) { this.handlers[name] = callback; }
            start() { this.state = "recording"; }
            stop() {
              this.state = "inactive";
              setTimeout(() => {
                this.handlers.dataavailable({data: new Blob(["sensitive-demo"], {type: "video/webm"})});
                this.handlers.stop();
              }, 75);
            }
          };
        })();""")
        self.page.goto(self.base + "/demo-center")
        self.page.locator("#recording-consent").check()
        self.page.locator("#record-start").click()
        expect(self.page.locator("#recording-status")).to_contain_text("RECORDING_LOCAL")
        self.page.locator("#recording-consent").uncheck()
        expect(self.page.locator("#recording-status")).to_contain_text("CONSENT_WITHDRAWN")
        expect(self.page.locator("#record-start")).to_be_disabled()
        self.page.wait_for_timeout(200)  # wait for deliberately delayed stale stop event
        expect(self.page.locator("#record-download")).to_be_hidden()
        expect(self.page.locator("#recording-status")).to_contain_text("CONSENT_WITHDRAWN")
        self.assertGreaterEqual(self.page.evaluate("window.__stoppedTracks"), 1)
        self.assertTrue(all(method == "GET" for method, _ in self.requests))

    def test_06_clear_disallows_delayed_blob_resurrection(self):
        self.page.add_init_script("""(() => {
          const track = { stop() {}, addEventListener() {} };
          Object.defineProperty(navigator.mediaDevices, "getDisplayMedia", {
            configurable: true,
            value: async () => ({getTracks: () => [track], getVideoTracks: () => [track]})
          });
          window.MediaRecorder = class {
            constructor() { this.state = "inactive"; this.mimeType = "video/webm"; this.handlers = {}; }
            static isTypeSupported(t) { return t === "video/webm"; }
            addEventListener(name, callback) { this.handlers[name] = callback; }
            start() { this.state = "recording"; }
            stop() {
              this.state = "inactive";
              setTimeout(() => {
                this.handlers.dataavailable({data: new Blob(["stale"], {type: "video/webm"})});
                this.handlers.stop();
              }, 75);
            }
          };
        })();""")
        self.page.goto(self.base + "/demo-center")
        self.page.locator("#recording-consent").check()
        self.page.locator("#record-start").click()
        expect(self.page.locator("#recording-status")).to_contain_text("RECORDING_LOCAL")
        self.page.locator("#record-clear").click()
        self.page.wait_for_timeout(200)
        expect(self.page.locator("#record-download")).to_be_hidden()
        expect(self.page.locator("#recording-status")).to_contain_text("CLEARED")
        self.assertTrue(all(method == "GET" for method, _ in self.requests))


    def test_07_twin_noc_demonstration_links_allow_browser_return(self):
        # Real Chromium navigation, not just anonymous HTTP 200 route checks.
        # The target remains synthetic and NOC data remains ACL-gated UNKNOWN.
        self.page.goto(self.base + "/demo-center")
        self.page.get_by_role("link", name="Voir le graphe existant").click()
        expect(self.page).to_have_url(self.base + "/demo/acme-impact")
        twin_nav = self.page.get_by_role("navigation", name="Parcours de démonstration")
        twin_nav.get_by_role("link", name="DemoCenter").click()
        expect(self.page).to_have_url(self.base + "/demo-center")
        self.page.get_by_role("link", name="Ouvrir NOC").click()
        expect(self.page).to_have_url(self.base + "/noc")
        expect(self.page.locator("#noc-state")).to_contain_text("UNKNOWN")
        expect(self.page.locator("#noc-rows")).to_contain_text("UNKNOWN")
        expect(self.page.locator("#noc-synthetic-status")).to_contain_text("SYNTHETIC_REFERENCE_ONLY")
        expect(self.page.locator("#noc-synthetic-path")).to_contain_text("SAN-FABRIC-A")
        expect(self.page.locator("#noc-synthetic-source")).to_contain_text("SHA-256")
        target = Path(os.environ.get("AIOPS_E2E_ARTIFACT_DIR", self.tmp.name))
        target.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(target / "noc-source-bridge-ci-synthetic.png"), full_page=True)
        self.page.get_by_role("link", name="Ouvrir le graphe synthétique").click()
        expect(self.page).to_have_url(self.base + "/demo/acme-impact")
        self.page.get_by_role("navigation", name="Parcours de démonstration").get_by_role("link", name="NOC (ACL requise)").click()
        expect(self.page).to_have_url(self.base + "/noc")
        noc_nav = self.page.get_by_role("navigation", name="Navigation opérateur")
        noc_nav.get_by_role("link", name="DemoCenter").click()
        expect(self.page).to_have_url(self.base + "/demo-center")
        self.assertTrue(all(method == "GET" for method, _ in self.requests))


    def test_08_home_noc_rejects_forged_200_without_independent_actor_tenant(self):
        # Browser-level regression: a 200 + tenant flag is NOT actor ACL,
        # runtime attestation or human/LIVE authority. Intercept on loopback.
        correlation = (
            '{"schema":"aiops.noc-canonical-correlation.v1",'
            '"state":"MATCHED_UNATTESTED",'
            '"source":"SIGNED_NOC_PAYLOAD_NOT_RUNTIME_ATTESTATION",'
            '"data_classification":"SYNTHETIC_CANONICAL_RUN",'
            '"tenant_acl_qualified":true,"actor_identity_server_derived":false,'
            '"runtime_authenticated":false,"production_qualified":false,'
            '"live_remediation_authorized":false,'
            '"canonical_run_id":"FORGED-SECRET-RUN"}'
        )
        grafana = (
            '{"schema":"aiops.noc-grafana-connectivity.v1",'
            '"state":"GRAFANA_HTTP_READY_UNATTESTED",'
            '"source":"REAL_GRAFANA_HTTP_HEALTH",'
            '"grafana_http_checked":true,"grafana_observation":"NOT_TESTED",'
            '"checkmk_thruk_observation":"NOT_TESTED",'
            '"tenant_acl_qualified":true,"actor_identity_server_derived":true,'
            '"runtime_authenticated":false,"production_qualified":false,'
            '"live_remediation_authorized":true,"secret":"FORGED-GRAFANA-SECRET"}'
        )
        self.page.route(
            "**/api/noc/correlation",
            lambda route: route.fulfill(
                status=200, content_type="application/json", body=correlation),
        )
        self.page.route(
            "**/api/noc/grafana-health",
            lambda route: route.fulfill(
                status=200, content_type="application/json", body=grafana),
        )
        self.page.goto(self.base + "/")
        self.page.locator("#noc-token").fill("disposable-viewer")
        self.page.get_by_role("button", name="Lire la corrélation").click()
        expect(self.page.locator("#noc-result")).to_contain_text("UNKNOWN")
        self.assertNotIn("FORGED-SECRET-RUN", self.page.locator("#noc-result").inner_text())
        self.page.locator("#noc-token").fill("disposable-viewer")
        self.page.get_by_role("button", name="Tester Grafana réel (HTTP)").click()
        expect(self.page.locator("#noc-grafana-result")).to_contain_text("UNKNOWN")
        self.assertNotIn("FORGED-GRAFANA-SECRET",
                         self.page.locator("#noc-grafana-result").inner_text())
        self.assertTrue(all(method == "GET" for method, _ in self.requests))


if __name__ == "__main__":
    unittest.main()
