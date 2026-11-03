"""P0 UX modernization: no manual browser bearer, only synthetic public data.

These tests qualify the disposable HTTP shell, NOT an authenticated Debian
operator session, a real GLPI/SSO integration or a production SAN observation.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "disposable-workspace-test-no-effect")

from portal import main, operator_workspace  # noqa: E402


class ModernWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def test_home_first_route_is_operator_workspace_and_never_reads_core(self):
        with patch.object(main, "get_json", side_effect=AssertionError("Core not queried")) as read:
            with patch.object(main, "read_portal_snapshot", side_effect=AssertionError("no upstream")):
                response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Comprendre l'incident", response.text)
        self.assertIn('id="impact-path"', response.text)
        self.assertIn('href="/demo-center"', response.text)
        self.assertIn('href="/noc"', response.text)
        self.assertIn('href="/demo-studio"', response.text)
        self.assertIn('href="/itsm"', response.text)
        self.assertIn('data-panel="runs"', response.text)
        self.assertIn("données opérationnelles", response.text.lower())
        self.assertNotIn('type="password"', response.text)
        self.assertNotIn('id="portal-read-token"', response.text)
        self.assertNotIn('id="noc-token"', response.text)
        self.assertNotIn('id="demo-token"', response.text)
        self.assertNotIn('Authorization: Bearer', response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("script-src 'self'", response.headers["content-security-policy"])
        self.assertNotIn("unsafe-inline", response.headers["content-security-policy"])
        read.assert_not_called()

    def test_named_views_reuse_shell_and_run_data_remains_protected(self):
        for path in ("/workspace", "/runs"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("operator-workspace.js", response.text)
            self.assertNotIn("portal-read-token", response.text)
        response = self.client.get("/api/portal/session")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["state"], "UNKNOWN")
        response = self.client.get("/api/portal/runs/RUN-SIM-UNKNOWN")
        self.assertNotEqual(response.status_code, 200)
        self.assertNotIn("ticket_id", response.text)

    def test_scripts_and_styles_same_origin_no_leak(self):
        css = self.client.get("/assets/operator-workspace.css")
        js = self.client.get("/assets/operator-workspace.js")
        self.assertEqual(css.status_code, 200)
        self.assertEqual(js.status_code, 200)
        self.assertIn("text/css", css.headers["content-type"])
        self.assertIn("javascript", js.headers["content-type"])
        self.assertIn("no-store", js.headers["cache-control"])
        self.assertIn('/api/demo/acme-impact', js.text)
        self.assertIn('/api/portal/session', js.text)
        self.assertIn('credentials: "same-origin"', js.text)
        self.assertIn('await finishSessionResponse(response)', js.text)
        self.assertIn('response.body.getReader()', js.text)
        self.assertIn('bytes > 8192', js.text)
        self.assertIn('credentials: "omit"', js.text)
        for bad in ("Authorization", "localStorage", "sessionStorage",
                    "innerHTML", "eval(", "getDisplayMedia"):
            self.assertNotIn(bad, js.text)
        self.assertNotIn("https://", css.text)

    def test_legacy_negative_script_remains_available_for_regression(self):
        response = self.client.get("/legacy")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="portal-read-token"', response.text)
        self.assertIn('id="noc-token"', response.text)
        self.assertNotIn("disposable-workspace-test-no-effect", response.text)

    def test_workspace_requires_immutable_local_fixture_authority(self):
        # Build does not contact Core/GLPI/Worker. It may be requested
        # anonymously only because it is an explicitly labelled fixture.
        from portal.acme_impact_read_model import build_acme_impact_read_model
        model = build_acme_impact_read_model()
        self.assertEqual(model["schema"], "aiops.synthetic-impact-read-model.v1")
        self.assertEqual(model["provenance"], "SIMULATED_TARGET")
        self.assertFalse(model["runtime_attested"])
        self.assertFalse(model["live_remediation_authorized"])
        self.assertIsNone(model["ticket_id"])
        self.assertEqual(model["entrypoint"], "/demo-center")


if __name__ == "__main__":
    unittest.main()
