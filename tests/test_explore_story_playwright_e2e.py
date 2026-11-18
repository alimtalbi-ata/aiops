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
        try:
            capture = getattr(self, "_capture_cockpit_diagnostic", None)
            if capture is not None:
                capture()
        finally:
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


    def test_04_readonly_aggregate_recipe_against_real_ephemeral_portal(self):
        """The CLI reads the actual portal HTTP API, not a mocked backend."""
        env = os.environ.copy()
        env["AIOPS_PORTAL_READ_TOKEN"] = VIEWER
        command = [sys.executable, str(ROOT / "scripts" / "qualify_acme_readonly.py"),
                   "--base-url", self.base]
        completed = subprocess.run(command, cwd=ROOT, env=env,
                                   capture_output=True, text=True, timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["contract_status"], "PASS")
        self.assertEqual(report["overall"], "NO_GO")
        self.assertEqual(report["scope"], "EPHEMERAL_PORTAL_SIMULATED_CONTRACT_ONLY")
        self.assertEqual(report["checkpoint_count"], 9)
        self.assertFalse(report["runtime_attested"])
        self.assertIn("CORE_TEMPORAL_ANALYST_CRITIC_POLICY_EVIDENCE_NOT_TESTED",
                      report["blockers"])
        self.assertNotIn(VIEWER, completed.stdout + completed.stderr)
        env.pop("AIOPS_PORTAL_READ_TOKEN")
        denied = subprocess.run(command, cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(denied.returncode, 2)
        self.assertEqual(json.loads(denied.stdout)["reason"], "missing_viewer_token")
        env["AIOPS_PORTAL_READ_TOKEN"] = VIEWER + "\nsecret"
        invalid = subprocess.run(command, cwd=ROOT, env=env,
                                 capture_output=True, text=True, timeout=20)
        self.assertEqual(invalid.returncode, 2)
        self.assertEqual(json.loads(invalid.stdout)["reason"], "invalid_viewer_token")
        self.assertNotIn("secret", invalid.stdout + invalid.stderr)

    def test_05_readonly_recipe_rejects_falsified_provenance_and_ids(self):
        """Negative contract tests use actual ephemeral portal response documents."""
        from copy import deepcopy
        from scripts.qualify_acme_readonly import (
            QualificationError, loopback_base, validate_pair,
        )
        impact = self.context.request.get(self.base + "/api/demo/acme-impact").json()
        story_response = self.context.request.post(
            self.base + "/api/demo/explore-story/control",
            headers={"Authorization": "Bearer " + VIEWER},
            data={"action": "start", "cursor": 0, "mode": "explore"},
        )
        self.assertEqual(story_response.status, 200)
        story = story_response.json()
        self.assertEqual(validate_pair(impact, story)["contract_status"], "PASS")
        for side, field, value in (
            ("impact", "provenance", "LIVE"),
            ("impact", "run_id", "RUN-FAKE"),
            ("impact", "ticket_id", "GLPI-REAL-CLAIM"),
            ("impact", "runtime_attested", True),
            ("story", "source_sha256", "0" * 64),
            ("story", "production_qualified", True),
        ):
            with self.subTest(side=side, field=field):
                left, right = deepcopy(impact), deepcopy(story)
                (left if side == "impact" else right)[field] = value
                with self.assertRaises(QualificationError):
                    validate_pair(left, right)
        for key, value in (
            ("status", "VERIFIED"),
            ("screenshot_sha256", "0" * 64),
            ("runtime_authenticated", True),
        ):
            with self.subTest(checkpoint=key):
                left = deepcopy(impact)
                left["checkpoint_evidence"][0][key] = value
                with self.assertRaises(QualificationError):
                    validate_pair(left, story)
        left = deepcopy(impact)
        left["decision_preview"]["policy"]["decision"] = "ALLOW_LIVE_ACTION"
        with self.assertRaises(QualificationError):
            validate_pair(left, story)
        right = deepcopy(story)
        right["scenario"]["incident_id"] = "OTHER-TENANT"
        with self.assertRaises(QualificationError):
            validate_pair(impact, right)
        for url in ("http://10.79.94.202:7777", "https://127.0.0.1:7777",
                    "http://localhost:7777", "http://127.0.0.1:7777/api/demo",
                    "http://127.0.0.1:secret"):
            with self.subTest(url=url), self.assertRaises(QualificationError):
                loopback_base(url)



    def test_06_aggregate_rejects_joint_target_and_synthetic_id_forgery(self):
        """Both HTTP projections may agree and still contradict the canonical target."""
        from copy import deepcopy
        from scripts.qualify_acme_readonly import QualificationError, validate_pair

        impact_response = self.context.request.get(self.base + "/api/demo/acme-impact")
        self.assertEqual(impact_response.status, 200)
        impact = impact_response.json()
        story_response = self.context.request.post(
            self.base + "/api/demo/explore-story/control",
            headers={"Authorization": "Bearer " + VIEWER},
            data={"action": "start", "cursor": 0, "mode": "explore"},
        )
        self.assertEqual(story_response.status, 200)
        story = story_response.json()
        self.assertEqual(validate_pair(impact, story)["overall"], "NO_GO")

        for field, forged, code in (
            ("simulation_ticket_id", "GLPI-REAL-123", "synthetic_ticket_binding_mismatch"),
            ("simulation_ticket_provenance", "REAL_GLPI", "synthetic_ticket_binding_mismatch"),
            ("evidence_source", "RUNTIME_EVIDENCE", "synthetic_source_provenance_mismatch"),
            ("simulation_timestamp_provenance", "RUNTIME_CLOCK",
             "synthetic_source_provenance_mismatch"),
        ):
            with self.subTest(field=field):
                changed = deepcopy(impact)
                changed[field] = forged
                with self.assertRaisesRegex(QualificationError, "^" + code + "$"):
                    validate_pair(changed, story)

        for field, forged in (("service", "temporal"), ("view", "live_recovery")):
            with self.subTest(joint_checkpoint_field=field):
                left, right = deepcopy(impact), deepcopy(story)
                left["checkpoint_evidence"][0][field] = forged
                right["timeline"][0][field] = forged
                with self.assertRaisesRegex(QualificationError, "^checkpoint_target_mismatch$"):
                    validate_pair(left, right)

        left = deepcopy(impact)
        left["checkpoint_evidence"][0]["required_state"] = "recovered"
        with self.assertRaisesRegex(QualificationError, "^checkpoint_target_mismatch$"):
            validate_pair(left, story)

        for field, forged in (
            ("provider", "NGX_MISTRAL_192B_RUNTIME"),
            ("analyst", {"status": "RUNTIME_VERIFIED"}),
            ("critic", {"decision": "APPROVE_LIVE"}),
        ):
            with self.subTest(decision_field=field):
                left = deepcopy(impact)
                left["decision_preview"][field] = forged
                with self.assertRaisesRegex(QualificationError, "^policy_preview_not_fail_closed$"):
                    validate_pair(left, story)


    def test_07_run_and_glpi_browser_fail_closed_without_tenant_acl(self):
        """Real ephemeral Chromium: no Run existence oracle or GLPI authority."""
        ids = ("RUN-FOREIGN-TENANT", "RUN-FORGED-999")
        projections = []
        for rid in ids:
            response = self.context.request.get(
                self.base + "/api/portal/runs/" + rid,
                headers={"Authorization": "Bearer " + VIEWER,
                         "X-Tenant-ID": "forged-tenant", "X-Actor-ID": "admin"},
            )
            self.assertEqual(response.status, 503)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
            projections.append(response.json())
        self.assertEqual(projections[0], projections[1])
        self.assertEqual(projections[0]["state"], "UNKNOWN")
        self.assertEqual(projections[0]["reason"], "TENANT_ACL_NOT_QUALIFIED")
        self.assertNotIn("run_id", projections[0])

        self.page.goto(self.base + "/runs/" + ids[0])
        expect(self.page.get_by_role("heading", name=re.compile("NOT VERIFIED"))).to_be_visible()
        self.assertIn("UNKNOWN", self.page.locator("body").inner_text())
        self.assertNotIn("CONNECTED", self.page.locator("body").inner_text())
        self.page.goto(self.base + "/itsm")
        expect(self.page.get_by_role("heading", name="GLPI / ITSM — point de passage opérateur")).to_be_visible()
        self.assertTrue(self.page.locator("#priority").is_disabled())
        self.assertIn("NOT_INSTALLED", self.page.locator("body").inner_text())
        status = self.context.request.get(
            self.base + "/api/portal/itsm",
            headers={"Authorization": "Bearer " + VIEWER},
        )
        self.assertEqual(status.status, 503)
        self.assertFalse(status.json()["glpi_write_enabled"])
        self.assertNotIn("CONNECTED", status.text())


    def test_08_customer_incident_cockpit_real_chromium_walkthrough_and_mobile(self):
        """Real browser checks the actual customer-facing SAN -> Payments page."""
        # tearDown invokes this before closing the browser context, even on
        # assertion failure. A diagnostic screenshot is not a PASS receipt.
        def retain_last_browser_state():
            output = Path(os.environ.get(
                "AIOPS_E2E_ARTIFACT_DIR", str(Path(self.tmp.name) / "artifacts")
            ))
            try:
                output.mkdir(parents=True, exist_ok=True)
                if not self.page.is_closed():
                    self.page.screenshot(
                        path=str(output / "acme-cockpit-debug-last-state.png"),
                        full_page=True, timeout=5000, animations="disabled",
                    )
            except Exception:
                # Never replace the original browser assertion failure.
                pass
        self._capture_cockpit_diagnostic = retain_last_browser_state
        response = self.page.goto(self.base + "/demo/acme-incident-cockpit")
        self.assertEqual(response.status, 200)
        expect(self.page.get_by_role("heading", name=re.compile("Parcours démontrable"))).to_be_visible()
        expect(self.page.locator("#verdict")).to_be_visible()
        self.assertEqual(self.page.locator("nav[aria-label='Parcours guidé de démonstration'] a[href^='#']").count(), 5)
        for anchor, heading in (
            ("impact", "Incident et impact métier"),
            ("workbench", "Evidence Workbench"),
            ("decision", "Analyst / Critic / Policy"),
            ("itil", "Transitions ITIL"),
            ("verdict", "Décision opérateur"),
        ):
            link = self.page.locator(f"nav a[href='#{anchor}']")
            self.assertEqual(link.count(), 1, anchor)
            link.click()
            self.assertEqual(self.page.evaluate("location.hash"), "#" + anchor)
            target = self.page.locator(f"#{anchor}")
            self.assertEqual(target.count(), 1)
            self.assertIn(heading, target.inner_text())
        # Historical fragment remains a direct link to the same evidence register.
        self.page.goto(self.base + "/demo/acme-incident-cockpit#evidence")
        self.assertEqual(self.page.evaluate("location.hash"), "#evidence")
        self.assertEqual(self.page.locator("#evidence").count(), 1)
        self.assertEqual(self.page.locator("#evidence + #workbench").count(), 1)
        expect(self.page.locator("#workbench")).to_be_visible()
        self.assertIn("GO — scénario synthétique", self.page.locator("body").inner_text())
        self.assertIn("UNKNOWN — preuves runtime", self.page.locator("body").inner_text())
        self.assertIn("NO-GO LIVE", self.page.locator("body").inner_text())
        self.assertEqual(self.page.locator("table").count(), 4)
        # Check each semantic table independently, not just the total number
        # of rows; a missing lifecycle stage cannot hide behind another table.
        self.assertEqual(
            [table.locator("tbody tr").count()
             for table in self.page.locator("table").all()],
            [9, 9, 9, 8],
        )
        self.assertEqual(self.page.locator("form").count(), 0)
        self.assertEqual(self.page.locator("script").count(), 0)

        # Capture the verified desktop view before switching to the mobile viewport.
        output = Path(os.environ.get(
            "AIOPS_E2E_ARTIFACT_DIR", str(Path(self.tmp.name) / "artifacts")
        ))
        output.mkdir(parents=True, exist_ok=True)
        desktop_png = self.page.screenshot(
            path=str(output / "acme-cockpit-desktop-ci-simulated.png"),
            full_page=True, animations="disabled",
        )
        self.assertEqual(desktop_png[:8], bytes((137, 80, 78, 71, 13, 10, 26, 10)))

        # Small viewport: tables remain inside scroll containers and summary cards stack.
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.reload()
        self.assertEqual(self.page.locator("div.table-scroll table").count(), 4)
        self.assertEqual(self.page.locator(".demo-card").count(), 3)
        self.assertEqual(
            [table.locator("tbody tr").count()
             for table in self.page.locator("table").all()],
            [9, 9, 9, 8],
        )
        self.assertIn("NO-GO LIVE", self.page.locator("#verdict").inner_text())
        self.assertTrue(self.page.locator("body").evaluate(
            "el => el.scrollWidth <= window.innerWidth"
        ), "cockpit creates page-level horizontal overflow on mobile")
        for wrapper in self.page.locator("div.table-scroll").all():
            self.assertGreaterEqual(
                wrapper.evaluate("el => el.scrollWidth"),
                wrapper.evaluate("el => el.clientWidth"),
            )

        # Preserve a customer-reviewable *synthetic* mobile browser observation.
        # It is never an authenticated runtime receipt or an approval to act.
        output = Path(os.environ.get(
            "AIOPS_E2E_ARTIFACT_DIR", str(Path(self.tmp.name) / "artifacts")
        ))
        output.mkdir(parents=True, exist_ok=True)
        screenshot = self.page.screenshot(
            path=str(output / "acme-cockpit-mobile-ci-simulated.png"),
            full_page=True, animations="disabled",
        )
        receipt = {
            "schema": "aiops.customer-cockpit-browser-observation.v1",
            "provenance": "CI_SIMULATED_EPHEMERAL_PORTAL",
            "viewport": {"width": 390, "height": 844},
            "route": "/demo/acme-incident-cockpit",
            "screenshot_file": "acme-cockpit-mobile-ci-simulated.png",
            "screenshot_sha256": hashlib.sha256(screenshot).hexdigest(),
            "desktop_screenshot_file": "acme-cockpit-desktop-ci-simulated.png",
            "desktop_screenshot_sha256": hashlib.sha256(desktop_png).hexdigest(),
            "fixture_sha256": re.search(
                r"[a-f0-9]{64}", self.page.locator("main").inner_text()
            ).group(0),
            "table_count": 4,
            "runtime_authenticated": False,
            "browser_rehearsal_independently_reviewed": False,
            "production_qualified": False,
            "live_remediation_authorized": False,
        }
        (output / "acme-cockpit-mobile-metadata.json").write_text(
            json.dumps(receipt, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        stored = json.loads((output / "acme-cockpit-mobile-metadata.json").read_text())
        self.assertEqual(
            hashlib.sha256((output / stored["screenshot_file"]).read_bytes()).hexdigest(),
            stored["screenshot_sha256"],
        )
        self.assertEqual(
            hashlib.sha256((output / stored["desktop_screenshot_file"]).read_bytes()).hexdigest(),
            stored["desktop_screenshot_sha256"],
        )
        self.assertFalse(stored["runtime_authenticated"])
        self.assertFalse(stored["browser_rehearsal_independently_reviewed"])
        self.assertFalse(stored["live_remediation_authorized"])



if __name__ == "__main__":
    unittest.main(verbosity=2)
