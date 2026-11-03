"""RG-UX-04/05/06: recovered DemoCenter route and no-upload recorder fences."""
import importlib
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "disposable-ci-only-no-live")


class DemoCenter386Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.portal = importlib.import_module("portal.main")
        cls.client = TestClient(cls.portal.app)

    def test_rg_ux_04_historical_routes_reused_not_reimplemented(self):
        routes = {route.path for route in self.portal.app.routes}
        for path in (
            "/demo-center", "/assets/demo-center-recorder.js",
            "/demo/explore-story", "/demo/acme-impact", "/noc", "/itsm",
        ):
            self.assertIn(path, routes)
        self.assertIn('href="/demo-center"', self.portal.home())
        self.assertIn('href="/noc"', self.portal.home())

    def test_rg_ux_05_public_shell_never_reads_backend_or_attests_runtime(self):
        with patch("shared.http.get_json", side_effect=AssertionError("upstream read")), \
             patch("shared.http.post_json", side_effect=AssertionError("upstream write")):
            response = self.client.get("/demo-center")
        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertEqual(html.count('<option value='), 8)
        for marker in ("SIMULATION_ONLY", "CATALOG_ONLY", "UNKNOWN",
                       "NOT_STARTED", "NOT_ATTESTED", "Aucun envoi réseau",
                       "/demo/acme-impact", "/demo/explore-story", "/noc", "/itsm"):
            self.assertIn(marker, html)
        self.assertNotIn("Bearer ", html)
        self.assertNotIn("TWIN_ACME_SIMULATED</", html)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("connect-src 'none'", response.headers["content-security-policy"])
        self.assertIn("media-src blob:", response.headers["content-security-policy"])
        self.assertIn("display-capture=(self)", response.headers["permissions-policy"])
        self.assertEqual(self.client.post("/demo-center").status_code, 405)

    def test_rg_ux_06_recorder_is_local_consent_and_secure_context_only(self):
        response = self.client.get("/assets/demo-center-recorder.js")
        self.assertEqual(response.status_code, 200)
        js = response.text
        for marker in ("getDisplayMedia", "MediaRecorder", "isSecureContext",
                       "recording-consent", "consent.checked", "URL.createObjectURL",
                       "URL.revokeObjectURL", "download.hidden = false",
                       "DENIED_OR_UNAVAILABLE", "BLOCKED_INSECURE_ORIGIN",
                       "audio: false", "textContent"):
            self.assertIn(marker, js)
        for forbidden in ("fetch(", "XMLHttpRequest", "sendBeacon", "localStorage",
                          "sessionStorage", "indexedDB", "innerHTML", "POST"):
            self.assertNotIn(forbidden, js)
        self.assertEqual(response.headers["cache-control"], "no-store")


if __name__ == "__main__":
    unittest.main()
