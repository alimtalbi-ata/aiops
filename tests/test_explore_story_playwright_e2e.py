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


    def test_08_glpi_human_readiness_ui_stays_unknown_and_actions_disabled(self):
        """Chromium sees a usable status check, not an unqualified ticket."""
        requests = []
        self.page.on("request", lambda request: requests.append(request.url))
        self.page.goto(self.base + "/itsm")
        expect(self.page.get_by_role("heading", name="Contrôle d'accès humain GLPI — lecture seule")).to_be_visible()
        self.assertIn("READMY", self.page.locator("body").inner_text())
        for action in ("Commenter", "Assigner", "Approuver HITL"):
            self.assertTrue(self.page.get_by_role("button", name=action).is_disabled())
        self.page.locator("#glpi-check").click()
        expect(self.page.locator("#glpi-check-status")).to_contain_text("401 UNAUTHORIZED")
        self.assertTrue(self.page.locator("#glpi-check").is_enabled())
        self.assertNotIn("CONNECTED", self.page.locator("#glpi-check-status").inner_text())
        self.assertTrue(any("/api/portal/itsm" in url for url in requests))
        self.assertFalse(any("/api/noc/runs/" in url for url in requests))
        self.assertFalse(any("/api/core/" in url for url in requests))
        self.assertFalse(any("/api/glpi/" in url for url in requests))
        self.assertFalse(any("token=" in url for url in requests))
        self.assertEqual(self.context.request.get(
            self.base + "/api/portal/itsm",
            headers={"Authorization": "Bearer " + VIEWER}).status, 503)


    def test_09_glpi_source_freshness_ui_rejects_forged_positive(self):
        """Real Chromium: source provenance is visible but never authorizes."""
        response = self.context.request.get(
            self.base + "/api/portal/itsm",
            headers={"Authorization": "Bearer " + VIEWER,
                     "X-GLPI-Permission": "READ",
                     "X-Core-Signed-Decision": "ALLOW"},
        )
        self.assertEqual(response.status, 503)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("frame-ancestors 'none'",
                      response.headers["content-security-policy"])
        body = response.json()
        self.assertEqual(body["authority_sources"]["provenance"],
                         "PORTAL_CONTRACT_ONLY")
        self.assertIsNone(body["authority_sources"]["observed_at"])
        self.assertEqual(body["authority_sources"]["freshness"], "UNKNOWN")
        self.assertEqual(body["authority_sources"]["core_pg16_producer"],
                         "SOURCE_CONTRACT_ONLY_NOT_HUMAN_ACL")
        self.assertFalse(body["authority_sources"]["independent_proofs_verified"])
        self.assertFalse(body["human_authority"]["human_allow"])
        self.assertNotIn("ticket_id", body)
        self.assertNotIn("run_id", body)

        requests = []
        self.page.on("request", lambda request: requests.append(request.url))
        self.page.goto(self.base + "/itsm")
        expect(self.page.locator("#glpi-source-provenance")).to_contain_text(
            "PORTAL_CONTRACT_ONLY")
        self.assertEqual(self.page.locator("[data-authority-check]").count(), 5)
        self.assertTrue(self.page.get_by_role("button", name="Approuver HITL").is_disabled())

        # This 503 is a test-controlled negative projection, NOT an IdP/GLPI
        # authenticated session. It exercises the UI renderer, not real ALLOW.
        self.page.route("**/api/portal/itsm", lambda route: route.fulfill(
            status=503, content_type="application/json", body=json.dumps(body)))
        self.page.locator("#glpi-check").click()
        expect(self.page.locator("#glpi-check-status")).to_contain_text("503 UNKNOWN")
        expect(self.page.locator('[data-authority-check="core"]')).to_contain_text(
            "source indépendante non attestée")
        self.page.unroute("**/api/portal/itsm")

        # An injected 200/CONNECTED/ALLOW cannot promote human authority or
        # place a forged ticket/Run in the browser, even on the same origin.
        self.page.route("**/api/portal/itsm", lambda route: route.fulfill(
            status=200, content_type="application/json",
            body=json.dumps({"state": "CONNECTED", "decision": "ALLOW",
                             "ticket_id": "FORGED-TICKET-999",
                             "run_id": "RUN-FORGED-999"})))
        self.page.locator("#glpi-check").click()
        expect(self.page.locator("#glpi-check-status")).to_contain_text(
            "503 UNKNOWN")
        expect(self.page.locator('[data-authority-check="idp"]')).to_contain_text(
            "réponse non qualifiée")
        self.assertNotIn("FORGED-TICKET-999", self.page.locator("body").inner_text())
        self.assertNotIn("CONNECTED", self.page.locator("#glpi-check-status").inner_text())
        self.assertNotIn("CONNECTED", self.page.locator("#glpi-source-readiness").inner_text())
        self.page.unroute("**/api/portal/itsm")

        self.assertTrue(self.page.get_by_role("button", name="Commenter").is_disabled())
        self.assertTrue(self.page.get_by_role("button", name="Assigner").is_disabled())
        self.assertTrue(self.page.get_by_role("button", name="Approuver HITL").is_disabled())
        self.assertFalse(any("/api/noc/runs/" in url or "/api/core/" in url
                             or "/api/glpi/" in url for url in requests))
        self.assertFalse(any("token=" in url for url in requests))

        output = Path(os.environ.get(
            "AIOPS_E2E_ARTIFACT_DIR", str(Path(self.tmp.name) / "artifacts")))
        output.mkdir(parents=True, exist_ok=True)
        checked_out_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        expected_head = os.environ.get("AIOPS_EXPECTED_HEAD_SHA")
        if expected_head:
            self.assertEqual(checked_out_head, expected_head)
        receipt = {
            "schema": "aiops.portal.glpi-source-freshness-negative.v1",
            "provenance": "CI_DISPOSABLE_SYNTHETIC_ONLY",
            "source_head": checked_out_head,
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "portal_api_http": 503,
            "portal_source_provenance": "PORTAL_CONTRACT_ONLY",
            "upstream_observed_at": None,
            "upstream_freshness": "UNKNOWN",
            "core_pg16_source_contract": "SOURCE_ONLY_NOT_HUMAN_ACL",
            "ui_negative_projection_cases": 2,
            "forged_positive_visible": False,
            "native_glpi_human_allow": False,
            "business_upstream_requests": 0,
            "host_7777_local_operator_reported": True,
            "external_tls_sso_unique_entrypoint_attested": False,
            "release_stable": "NO_GO",
        }
        canonical = json.dumps(receipt, sort_keys=True,
                               separators=(",", ":")).encode("utf-8")
        receipt["payload_sha256"] = hashlib.sha256(canonical).hexdigest()
        (output / "portal-glpi-source-freshness-negative.json").write_text(
            json.dumps(receipt, sort_keys=True, indent=2) + "\n",
            encoding="utf-8")



    def test_10_glpi_readmy_ticket_user_boundary_browser_401_403_503(self):
        """Real Chromium/HTTP, no positive human permission or ticket exposure."""
        denied = self.context.request.get(self.base + "/api/portal/itsm")
        self.assertEqual(denied.status, 401)
        unknown = self.context.request.get(self.base + "/api/portal/itsm",
            headers={"Authorization": "Bearer " + VIEWER,
                     "X-GLPI-Ticket-User": "77",
                     "X-GLPI-Permission": "READMY",
                     "X-Core-Decision": "ALLOW"})
        self.assertEqual(unknown.status, 503)
        body = unknown.json()
        self.assertEqual(body["human_authority"]["readmy_ticket_user_membership"],
                         "UNKNOWN")
        self.assertEqual(body["authority_sources"][
            "glpi_native_ticket_user_membership"], "NOT_ATTESTED")
        self.assertFalse(body["authority_sources"]["independent_proofs_verified"])
        self.assertNotIn("ticket_id", body)
        self.assertNotIn("run_id", body)
        self.assertEqual(unknown.headers["cache-control"], "no-store")

        requested = []
        self.page.on("request", lambda req: requested.append(req.url))
        self.page.goto(self.base + "/itsm")
        ownership = self.page.locator('[data-authority-check="ownership"]')
        expect(ownership).to_contain_text("UNKNOWN")
        self.assertEqual(self.page.locator("[data-authority-check]").count(), 5)
        self.assertIn("Ticket_User", self.page.locator(
            "#human-rights-title").locator("xpath=..").inner_text())

        # Even forged same-origin 200/ALLOW with native-looking ownership
        # and a Core signature is never rendered as an authorization.
        self.page.route("**/api/portal/itsm", lambda route: route.fulfill(
            status=200, content_type="application/json",
            body=json.dumps({"state": "CONNECTED", "decision": "ALLOW",
                             "glpi_right": "READMY", "ticket_user": 77,
                             "ticket_id": "FORGED-TICKET-999",
                             "run_id": "RUN-FORGED-999",
                             "core_signature": "FORGED"})))
        self.page.locator("#glpi-check").click()
        expect(self.page.locator("#glpi-check-status")).to_contain_text(
            "503 UNKNOWN")
        expect(ownership).to_contain_text("réponse non qualifiée")
        self.assertNotIn("FORGED-TICKET-999", self.page.locator("body").inner_text())
        self.assertNotIn("RUN-FORGED-999", self.page.locator("body").inner_text())
        self.page.unroute("**/api/portal/itsm")

        # A native-looking negative body cannot grant; explicit 401 and
        # 403 remain visibly denied without a browser viewer fallback.
        def denied_route(status_code):
            # Playwright may pass (route, request) positionally; do not
            # capture the status as a callback default argument.
            def fulfill(route):
                route.fulfill(status=status_code, content_type="application/json",
                              body=json.dumps({"state": "UNAUTHORIZED"}))
            return fulfill

        for code, expected in ((401, "401 UNAUTHORIZED"),
                               (403, "403 FORBIDDEN")):
            with self.subTest(http=code):
                self.page.route("**/api/portal/itsm", denied_route(code))
                self.page.locator("#glpi-check").click()
                expect(self.page.locator("#glpi-check-status")).to_contain_text(
                    expected)
                expect(ownership).to_contain_text("UNKNOWN")
                self.page.unroute("**/api/portal/itsm")

        for name in ("Commenter", "Assigner", "Approuver HITL"):
            self.assertTrue(self.page.get_by_role("button", name=name).is_disabled())
        self.assertFalse(any("/api/core/" in url or "/api/glpi/" in url
                             or "/api/noc/runs/" in url for url in requested))
        self.assertFalse(any("token=" in url for url in requested))

        output = Path(os.environ.get(
            "AIOPS_E2E_ARTIFACT_DIR", str(Path(self.tmp.name) / "artifacts")))
        output.mkdir(parents=True, exist_ok=True)
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        expected = os.environ.get("AIOPS_EXPECTED_HEAD_SHA")
        if expected:
            self.assertEqual(head, expected)
        receipt = {
            "schema": "aiops.portal.glpi-readmy-browser-negative.v1",
            "source_head": head,
            "provenance": "CI_DISPOSABLE_SYNTHETIC_ONLY",
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "readmy_ticket_user_authority": "NOT_ATTESTED",
            "core_run_binding_authority": "NOT_ATTESTED",
            "api_missing_identity_http": 401,
            "api_viewer_without_native_glpi_http": 503,
            "injected_http_cases": [200, 401, 403],
            "forged_positive_visible": False,
            "business_upstream_requests": 0,
            "human_allow": False,
            "host_local_7777_operator_reported": True,
            "external_https_sso_glpi_unique_entrypoint_attested": False,
            "release_stable": "NO_GO",
        }
        canonical = json.dumps(receipt, sort_keys=True,
                               separators=(",", ":")).encode("utf-8")
        receipt["payload_sha256"] = hashlib.sha256(canonical).hexdigest()
        (output / "portal-glpi-readmy-browser-negative.json").write_text(
            json.dumps(receipt, sort_keys=True, indent=2) + "\n",
            encoding="utf-8")



    def test_11_glpi_explicit_403_denial_browser_and_no_positive_authority(self):
        """Real disposable Chromium: 401/403/503 are distinct; 200 never grants."""
        anonymous = self.context.request.get(self.base + "/api/portal/itsm")
        self.assertEqual(anonymous.status, 401)
        viewer = self.context.request.get(
            self.base + "/api/portal/itsm",
            headers={"Authorization": "Bearer " + VIEWER,
                     "X-GLPI-Permission": "READMY",
                     "X-Core-Decision": "ALLOW"})
        self.assertEqual(viewer.status, 503)
        self.assertFalse(viewer.json()["human_authority"]["human_allow"])
        self.assertEqual(viewer.json()["authority_sources"]["freshness"], "UNKNOWN")

        observed = []
        self.page.on("request", lambda request: observed.append(request.url))
        self.page.goto(self.base + "/itsm")
        self.assertTrue(self.page.get_by_role("button", name="Approuver HITL").is_disabled())
        def route_for(code, body):
            def handler(route):
                route.fulfill(status=code, content_type="application/json",
                              body=json.dumps(body))
            return handler

        cases = (
            (401, {"state": "UNAUTHORIZED"}, "401 UNAUTHORIZED", "session non autorisée"),
            (403, {"state": "UNAUTHORIZED"}, "403 FORBIDDEN", "accès refusé"),
            (503, {"state": "UNKNOWN"}, "503 UNKNOWN", "contrat de source non qualifié"),
            (200, {"state": "CONNECTED", "decision": "ALLOW",
                   "ticket_id": "FORGED-TICKET-999",
                   "run_id": "RUN-FORGED-999"}, "503 UNKNOWN", "réponse non qualifiée"),
        )
        for code, body, status_text, source_text in cases:
            with self.subTest(injected_http=code):
                handler = route_for(code, body)
                self.page.route("**/api/portal/itsm", handler)
                self.page.locator("#glpi-check").click()
                expect(self.page.locator("#glpi-check-status")).to_contain_text(status_text)
                expect(self.page.locator('[data-authority-check="idp"]')).to_contain_text(
                    source_text)
                expect(self.page.locator("#glpi-check")).to_be_enabled()
                for action in ("Commenter", "Assigner", "Approuver HITL"):
                    self.assertTrue(self.page.get_by_role("button", name=action).is_disabled())
                self.assertNotIn("FORGED-TICKET-999", self.page.locator("body").inner_text())
                self.assertNotIn("RUN-FORGED-999", self.page.locator("body").inner_text())
                self.page.unroute("**/api/portal/itsm", handler)

        self.assertFalse(any("/api/core/" in url or "/api/glpi/" in url
                             or "/api/noc/runs/" in url or "token=" in url
                             for url in observed))
        output = Path(os.environ.get(
            "AIOPS_E2E_ARTIFACT_DIR", str(Path(self.tmp.name) / "artifacts")))
        output.mkdir(parents=True, exist_ok=True)
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        expected = os.environ.get("AIOPS_EXPECTED_HEAD_SHA")
        if expected:
            self.assertEqual(head, expected)
        receipt = {
            "schema": "aiops.portal.glpi-explicit-denial-browser.v1",
            "source_head": head,
            "provenance": "CI_DISPOSABLE_SYNTHETIC_ONLY",
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "api_anonymous_http": 401,
            "api_viewer_without_native_glpi_http": 503,
            "browser_injected_statuses": [401, 403, 503, 200],
            "explicit_403_displayed_as": "403 FORBIDDEN",
            "forged_positive_visible": False,
            "human_allow": False,
            "business_upstream_requests": 0,
            "host_local_7777_operator_reported": True,
            "external_tls_sso_glpi_unique_entrypoint_attested": False,
            "release_stable": "NO_GO",
        }
        canonical = json.dumps(receipt, sort_keys=True,
                               separators=(",", ":")).encode("utf-8")
        receipt["payload_sha256"] = hashlib.sha256(canonical).hexdigest()
        (output / "portal-glpi-explicit-denial-browser.json").write_text(
            json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")



class PortalHttps7777ChromiumE2E(unittest.TestCase):
    """Real disposable HTTPS/Chromium origin :7777, NOT a Debian TLS claim."""

    def test_https_7777_browser_glpi_unknown_and_callback_host_fence(self):
        import ssl
        from urllib.parse import parse_qs
        from portal_core_signed_glpi_fixture import _cert

        with tempfile.TemporaryDirectory(prefix="portal-https-7777-ci-") as tmp:
            cert, key = _cert(Path(tmp), "127.0.0.1")
            base = "https://127.0.0.1:7777"
            env = os.environ.copy()
            env.update({
                "PYTHONPATH": str(ROOT / "app"),
                "AIOPS_INTERNAL_TOKEN": "ci-only-internal-ephemeral-token",
                "AIOPS_PORTAL_READ_TOKEN": VIEWER,
                "CORE_URL": "http://127.0.0.1:9",
                "COPILOT_URL": "http://127.0.0.1:9",
                "TWIN_URL": "http://127.0.0.1:9",
                "AIOPS_PORTAL_OIDC_ISSUER": "https://idp.example.test/realms/acme",
                "AIOPS_PORTAL_OIDC_AUTHORIZATION_ENDPOINT":
                    "https://idp.example.test/realms/acme/protocol/openid-connect/auth",
                "AIOPS_PORTAL_OIDC_TOKEN_ENDPOINT":
                    "https://idp.example.test/realms/acme/protocol/openid-connect/token",
                "AIOPS_PORTAL_OIDC_CLIENT_ID": "aiops2-portal",
                "AIOPS_PORTAL_OIDC_AUDIENCE": "aiops2-portal",
                "AIOPS_PORTAL_OIDC_REDIRECT_URI":
                    base + "/auth/oidc/callback",
            })
            with open(Path(tmp) / "portal-tls.log", "w+b") as log:
                server = subprocess.Popen(
                    [sys.executable, "-m", "uvicorn", "portal.main:app",
                     "--host", "127.0.0.1", "--port", "7777",
                     "--ssl-certfile", str(cert), "--ssl-keyfile", str(key)],
                    cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
                try:
                    pinned = ssl.create_default_context(cafile=str(cert))
                    pinned.check_hostname = False  # disposable self-signed IP fixture
                    for _ in range(60):
                        if server.poll() is not None:
                            raise RuntimeError("disposable HTTPS portal exited")
                        try:
                            with urlopen(base + "/health", timeout=1,
                                         context=pinned) as health:
                                if health.status == 200:
                                    break
                        except (OSError, ssl.SSLError):
                            pass
                        time.sleep(0.25)
                    else:
                        raise RuntimeError("disposable HTTPS portal not ready")

                    with sync_playwright() as pw:
                        browser = pw.chromium.launch(
                            headless=True, args=["--no-sandbox"])
                        try:
                            context = browser.new_context(
                                ignore_https_errors=True,
                                service_workers="block",
                                accept_downloads=False)
                            try:
                                observed = []
                                def fence(route):
                                    u = urlsplit(route.request.url)
                                    observed.append(route.request.url)
                                    if (u.scheme == "https"
                                            and u.hostname == "127.0.0.1"
                                            and u.port == 7777
                                            and route.request.method in ("GET", "POST")):
                                        route.continue_()
                                    else:
                                        route.abort()
                                context.route("**/*", fence)
                                page = context.new_page()
                                shell = page.goto(base + "/itsm")
                                self.assertEqual(shell.status, 200)
                                self.assertEqual(
                                    page.locator("[data-authority-check]").count(), 5)
                                page.locator("#glpi-check").click()
                                expect(page.locator("#glpi-check-status")).to_contain_text(
                                    "401 UNAUTHORIZED")
                                for action in ("Commenter", "Assigner", "Approuver HITL"):
                                    self.assertTrue(page.get_by_role(
                                        "button", name=action).is_disabled())
                                self.assertFalse(any(
                                    "/api/core/" in u or "/api/glpi/" in u
                                    or "/api/noc/runs/" in u for u in observed))

                                login = context.request.get(
                                    base + "/auth/oidc/login", max_redirects=0)
                                self.assertEqual(login.status, 303)
                                self.assertIn("Secure", login.headers["set-cookie"])
                                location = urlsplit(login.headers["location"])
                                self.assertEqual(parse_qs(location.query)[
                                    "redirect_uri"], [base + "/auth/oidc/callback"])
                                self.assertTrue(any(
                                    c["name"] == "__Host-aiops_portal_oidc_state"
                                    for c in context.cookies(base)))
                                # HTTPS connection remains :7777, but a forged
                                # Host :17777 must never consume callback state.
                                state = parse_qs(location.query)["state"][0]
                                alias = context.request.get(
                                    base + "/auth/oidc/callback",
                                    params={"code": "disposable", "state": state},
                                    headers={"Host": "127.0.0.1:17777"},
                                    max_redirects=0)
                                self.assertEqual(alias.status, 401)
                                self.assertEqual(alias.json()["state"], "UNKNOWN")
                                self.assertNotIn("set-cookie", alias.headers)
                                same = context.request.post(
                                    base + "/api/portal/run-session",
                                    headers={"Authorization": "Bearer " + VIEWER,
                                             "Origin": base,
                                             "X-Portal-Run-ID": "RUN-ACME-123"})
                                self.assertEqual(same.status, 503)
                                self.assertFalse(same.json()["tenant_acl_qualified"])
                                for origin in ("https://127.0.0.1:17777",
                                               "http://127.0.0.1:7777"):
                                    denied = context.request.post(
                                        base + "/api/portal/run-session",
                                        headers={"Authorization": "Bearer " + VIEWER,
                                                 "Origin": origin,
                                                 "X-Portal-Run-ID": "RUN-ACME-123"})
                                    self.assertEqual(denied.status, 403)
                                    self.assertNotIn("set-cookie", denied.headers)
                            finally:
                                context.close()
                        finally:
                            browser.close()
                finally:
                    server.terminate()
                    try:
                        server.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=5)

            output = Path(os.environ.get(
                "AIOPS_E2E_ARTIFACT_DIR", str(Path(tmp) / "artifacts")))
            output.mkdir(parents=True, exist_ok=True)
            head = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
            expected = os.environ.get("AIOPS_EXPECTED_HEAD_SHA")
            if expected:
                self.assertEqual(head, expected)
            receipt = {
                "schema": "aiops.portal.https7777-disposable-chromium.v1",
                "source_head": head,
                "provenance": "CI_DISPOSABLE_SYNTHETIC_ONLY",
                "observed_at_utc": datetime.now(timezone.utc).isoformat(),
                "loopback_https_7777_browser_shell_http": 200,
                "glpi_api_no_oidc_http": 401,
                "oidc_login_redirect_http": 303,
                "forged_callback_host_17777_http": 401,
                "run_session_https_7777_without_human_acl_http": 503,
                "run_session_alias_17777_or_http_origin_http": 403,
                "glpi_native_human_allow": False,
                "business_upstream_requests": 0,
                "debian_local_7777_operator_reported": True,
                "debian_external_tls_sso_glpi_uniqueness_attested": False,
                "release_stable": "NO_GO",
            }
            canonical = json.dumps(receipt, sort_keys=True,
                                   separators=(",", ":")).encode("utf-8")
            receipt["payload_sha256"] = hashlib.sha256(canonical).hexdigest()
            (output / "portal-https7777-disposable-chromium.json").write_text(
                json.dumps(receipt, sort_keys=True, indent=2) + "\n",
                encoding="utf-8")


# Quality browser entry point also runs the disposable negative Portal ACL suite.
from test_portal_acl_browser_e2e import PortalACLChromiumE2E
# Run the Portal actor-resource contract suite at the same exact CI SHA.
# This is test-only wiring; no shared Quality workflow is modified.
from test_portal_core_acl_consumer import PortalCoreACLConsumerTests
# Focused disposable IdP/GLPI/Core signer rotation suite (no shared CI edit).
from test_portal_idp_glpi_rotation_contract import PortalIdpGlpiRotationContract

# Portal-only Host/OIDC downgrade contract: imported into existing Quality browser entry.
from test_portal_host_cookie_negative_contract import PortalHostCookieNegativeContract

if __name__ == "__main__":
    unittest.main(verbosity=2)
