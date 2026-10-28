"""Real Chromium -> ephemeral FastAPI portal Explore/Story E2E.

The browser and portal are real local processes. Scenario data is strictly
SIMULATED_TARGET. No upstream Core/GLPI/Temporal/n8n, LIVE or Debian access.
The screenshot is a CI UI observation, never an authenticated LIVE receipt.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from urllib.request import urlopen
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
VIEWER = "ci-e2e-explore-viewer-token-only"


class ExploreStoryChromiumE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="aiops-explore-browser-")
        cls.log = open(Path(cls.tmp.name) / "portal.log", "w+b")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        env = os.environ.copy()
        env.update({
            "PYTHONPATH": str(ROOT / "app"),
            "AIOPS_INTERNAL_TOKEN": "ci-only-internal-ephemeral-token",
            "AIOPS_PORTAL_READ_TOKEN": VIEWER,
            # Accidental upstream requests must fail, not contact external services.
            "CORE_URL": "http://127.0.0.1:9",
            "COPILOT_URL": "http://127.0.0.1:9",
            "TWIN_URL": "http://127.0.0.1:9",
        })
        cls.server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "portal.main:app",
             "--host", "127.0.0.1", "--port", str(cls.port)],
            cwd=ROOT, env=env, stdout=cls.log, stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(60):
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
                raise RuntimeError("ephemeral portal did not become ready")
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
            viewport={"width": 1365, "height": 900},
        )
        # Only the ephemeral loopback portal may be reached by this browser.
        def fence(route):
            url = urlsplit(route.request.url)
            if (url.scheme == "http" and url.hostname == "127.0.0.1"
                    and url.port == self.port
                    and route.request.method in ("GET", "POST")):
                route.continue_()
            else:
                route.abort()
        self.context.route("**/*", fence)
        self.page = self.context.new_page()

    def tearDown(self):
        self.context.close()

    def test_01_anonymous_shell_and_real_http_auth_refusal(self):
        self.page.goto(self.base + "/demo/explore-story")
        expect(self.page.locator("#story-status")).to_contain_text("UNKNOWN")
        self.assertNotIn("SIM-ACME-", self.page.content())
        self.page.locator("#start").click()
        expect(self.page.locator("#story-status")).to_contain_text("jeton viewer requis")
        response = self.context.request.post(
            self.base + "/api/demo/explore-story/control",
            data={"action": "start", "cursor": 0, "mode": "story"},
        )
        self.assertEqual(response.status, 401)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_02_wrong_token_never_renders_scenario(self):
        self.page.goto(self.base + "/demo/explore-story")
        self.page.locator("#story-token").fill("wrong-ci-only-token")
        self.page.locator("#start").click()
        expect(self.page.locator("#story-status")).to_contain_text("contrôle refusé (401)")
        self.assertNotIn("SIM-ACME-", self.page.locator("#scenario").inner_text())
        self.assertEqual(self.page.locator("#story-token").input_value(), "")

    def test_03_explore_story_impact_and_unattested_browser_capture(self):
        self.page.goto(self.base + "/demo/explore-story")
        self.page.locator("#story-token").fill(VIEWER)
        self.page.locator("#start").click()
        expect(self.page.locator("#story-status")).to_contain_text("PAUSE / EXPLORE")
        scenario = self.page.locator("#scenario").inner_text()
        run_id = scenario.split(" · ")[0]
        self.assertRegex(run_id, r"^SIM-ACME-[A-F0-9]{16}$")
        self.assertIn("ACME-DEMO-SAN-001", scenario)
        self.assertIn("ACME-DEMO-PAY-002", scenario)
        self.assertEqual(self.page.locator("#timeline li").count(), 9)
        self.assertEqual(self.page.locator("#story-token").input_value(), "")
        self.page.locator("#advance").click()
        expect(self.page.locator("#story-status")).to_contain_text("2/9")
        self.assertIn("MISSING", self.page.locator("#step-detail").inner_text())

        # A different real portal route must use the same synthetic Run ID.
        self.page.goto(self.base + "/demo/acme-impact")
        expect(self.page.locator("body")).to_contain_text(run_id)
        self.page.goto(self.base + "/demo/explore-story")
        self.page.locator("#mode-story").click()
        self.page.locator("#story-token").fill(VIEWER)
        self.page.locator("#start").click()
        expect(self.page.locator("#story-status")).to_contain_text("STORY EN COURS")
        self.page.locator("#pause").click()
        expect(self.page.locator("#story-status")).to_contain_text("PAUSE / EXPLORE")
        self.assertIn(run_id, self.page.locator("#scenario").inner_text())
        self.assertEqual(self.page.locator("#timeline li").count(), 9)
        self.assertTrue(all(
            "MISSING" in text for text in self.page.locator("#timeline li").all_inner_texts()
        ))
        self.assertEqual(self.page.locator("#story-token").input_value(), "")
        self.assertNotIn(VIEWER, self.page.content())
        # Real Chromium layout regression: a 64-character fixture digest must
        # stay inside its card, not overlap the adjacent checkpoint panel.
        self.assertTrue(self.page.locator("#source").evaluate(
            "el => el.scrollWidth <= el.clientWidth"
        ), "fixture SHA overflows the scenario card")

        output = Path(os.environ.get(
            "AIOPS_E2E_ARTIFACT_DIR", str(Path(self.tmp.name) / "artifacts")
        ))
        output.mkdir(parents=True, exist_ok=True)
        screenshot = self.page.screenshot(
            path=str(output / "explore-story-ci-simulated.png"),
            full_page=True, animations="disabled",
        )
        digest = re.search(r"[a-f0-9]{64}", self.page.locator("#source").inner_text())
        self.assertIsNotNone(digest)
        receipt = {
            "schema": "aiops.ci-browser-observation.v1",
            "provenance": "CI_SIMULATED_PORTAL",
            "capture_method": "PLAYWRIGHT_CHROMIUM_EPHEMERAL_PORTAL",
            "source_url": self.base + "/demo/explore-story",
            "source_fixture_sha256": digest.group(0),
            "run_id": run_id,
            "incident_id": "ACME-DEMO-SAN-001",
            "impact_incident_id": "ACME-DEMO-PAY-002",
            "glpi_ticket_id": None,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_sha": os.environ.get("GITHUB_SHA"),
            "screenshot_file": "explore-story-ci-simulated.png",
            "screenshot_sha256": hashlib.sha256(screenshot).hexdigest(),
            "runtime_authenticated": False,
            "production_qualified": False,
            "live_remediation_authorized": False,
            "privacy_reviewed": False,
        }
        (output / "capture-metadata.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.page.locator("#clear").click()
        expect(self.page.locator("#story-status")).to_contain_text("session effacée")
        self.assertNotIn("SIM-ACME-", self.page.locator("#scenario").inner_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
