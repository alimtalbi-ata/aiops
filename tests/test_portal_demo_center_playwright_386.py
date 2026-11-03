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
        self.page.add_init_script("""() => {
          Object.defineProperty(navigator.mediaDevices, "getDisplayMedia", {
            configurable: true, value: async () => { throw new DOMException("Denied", "NotAllowedError"); }
          });
        }""")
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
        self.page.add_init_script("""() => {
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
        }""")
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


if __name__ == "__main__":
    unittest.main()
