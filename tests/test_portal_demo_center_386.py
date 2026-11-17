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

    def test_rg_ux_08_twin_entrypoint_is_same_origin_demonstration_route(self):
        # The previous 10.79.x.x:17777 candidate address was not the
        # canonical :7777 portal and could misdirect the demo operator.
        # The fixture remains synthetic; this is navigation, not authority.
        with patch("shared.http.get_json", side_effect=AssertionError("upstream read")), \
             patch("shared.http.post_json", side_effect=AssertionError("upstream write")):
            response = self.client.get("/api/demo/acme-impact")
        self.assertEqual(response.status_code, 200)
        model = response.json()
        self.assertEqual(model["entrypoint"], "/demo-center")
        self.assertEqual(model["provenance"], "SIMULATED_TARGET")
        self.assertFalse(model["runtime_attested"])
        self.assertFalse(model["live_remediation_authorized"])
        self.assertNotIn("://", model["entrypoint"])
        self.assertIn('href="/demo/acme-impact"', self.client.get("/demo-center").text)

    def test_rg_ux_09_twin_noc_demo_navigation_is_read_only_and_same_origin(self):
        # The Twin page previously had no way back to DemoCenter or onward to NOC.
        # These are existing same-origin GET routes, not an authority or action.
        with patch("shared.http.get_json", side_effect=AssertionError("upstream read")), \
             patch("shared.http.post_json", side_effect=AssertionError("upstream write")):
            twin = self.client.get("/demo/acme-impact")
            noc = self.client.get("/noc")
        self.assertEqual(twin.status_code, 200)
        self.assertEqual(noc.status_code, 200)
        for target in ('href="/demo-center"', 'href="/noc"',
                       'href="/demo/explore-story"', 'href="/itsm"'):
            self.assertIn(target, twin.text)
        self.assertIn('aria-label="Parcours de démonstration"', twin.text)
        self.assertIn("focus-visible", twin.text)
        self.assertIn('href="/demo-center"', noc.text)
        self.assertNotIn(":17777", twin.text)
        self.assertIn("SIMULATION LOCALE UNIQUEMENT", twin.text)
        self.assertEqual(self.client.post("/demo/acme-impact").status_code, 405)

    def test_rg_ux_13_recorder_station_is_same_origin_and_no_backend_io(self):
        # A recorder inside the navigating tab dies on pagehide. The existing
        # recorder can instead stay alive in a second tab; no new recorder API.
        with patch("shared.http.get_json", side_effect=AssertionError("upstream read")), \
             patch("shared.http.post_json", side_effect=AssertionError("upstream write")):
            home = self.client.get("/demo-center")
            station = self.client.get("/demo-center/recorder")
        self.assertEqual(home.status_code, 200)
        self.assertEqual(station.status_code, 200)
        self.assertIn('href="/demo-center/recorder" target="_blank" rel="noopener noreferrer"', home.text)
        self.assertIn("Poste de capture locale", station.text)
        self.assertIn('id="record-start"', station.text)
        self.assertIn('src="/assets/demo-center-recorder.js"', station.text)
        self.assertIn("LOCAL_ONLY / NO LIVE EFFECT", station.text)
        self.assertIn("SIMULATION_ONLY", station.text)
        self.assertEqual(station.headers["cache-control"], "no-store")
        self.assertIn("connect-src 'none'", station.headers["content-security-policy"])
        self.assertEqual(self.client.post("/demo-center/recorder").status_code, 405)

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
