"""HTTP shell and static JS safety checks; no live browser/runtime attestation."""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "ci-test-internal-token-not-production")

from fastapi.testclient import TestClient
from portal.main import app

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


class OperatorConsoleTests(unittest.TestCase):
    def test_route_mounted_and_hardened(self):
        response = client.get("/operator")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Incident / Run / Evidence", response.text)
        self.assertIn('id="incidents-state"', response.text)
        self.assertIn('id="evidence-state"', response.text)
        self.assertIn("UNKNOWN", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertIn("connect-src 'self'", response.headers["content-security-policy"])
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
        self.assertNotIn("<script>", response.text)

    def test_javascript_asset_no_cache_and_same_origin(self):
        response = client.get("/operator/console.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/javascript", response.headers["content-type"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        js = response.text
        self.assertIn('fetch("/api/portal/operator/snapshot"', js)
        self.assertIn('credentials: "omit"', js)
        self.assertIn('cache: "no-store"', js)
        self.assertIn('redirect: "error"', js)
        self.assertIn("textContent", js)
        self.assertIn("replaceChildren", js)
        self.assertIn("requestedGeneration !== generation", js)
        for forbidden in ("localStorage", "sessionStorage", "document.cookie",
                          "innerHTML", "eval(", "window.location ="):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, js)

    def test_console_does_not_bypass_api_rbac(self):
        response = client.get("/api/portal/operator/snapshot")
        self.assertIn(response.status_code, (401, 503))
        self.assertNotIn("items", response.text)

    def test_home_navigation_exposes_console_not_fake_live(self):
        # Source-level navigation assertion avoids probing unavailable Core/Twin.
        source = (ROOT / "app/portal/main.py").read_text()
        self.assertIn('href="/operator"', source)
        self.assertIn("Synthetic/demo data is explicitly labelled", source)

    def test_operator_page_does_not_embed_credentials_or_upstream_data(self):
        response = client.get("/operator")
        self.assertNotIn("AIOPS_PORTAL_READ_TOKEN", response.text)
        self.assertNotIn("AIOPS_PORTAL_OPERATOR_TOKEN", response.text)
        self.assertNotIn("http://aiops2-core", response.text)
        self.assertNotIn("http://aiops2-evidence", response.text)
        self.assertNotIn("localStorage", response.text)


if __name__ == "__main__":
    unittest.main()
