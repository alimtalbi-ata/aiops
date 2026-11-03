"""RG-UX-01/02/03: NOC operator UI fail-closed contract, no mock PASS."""
import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "disposable-only-not-live")

class NocOperatorUXTests(unittest.TestCase):
    def test_rg_ux_01_dedicated_route_and_navigation(self):
        portal = importlib.import_module("portal.main")
        paths = {r.path for r in portal.app.routes}
        self.assertIn("/noc", paths)
        self.assertIn("/assets/noc-operator.js", paths)
        self.assertIn('href="/noc"', portal.home())

    def test_rg_ux_02_no_unqualified_data_or_live_controls(self):
        module = importlib.import_module("portal.noc_operator_page")
        with patch("portal.noc_runtime._read_model", side_effect=AssertionError("unexpected I/O"), create=True):
            response = module.noc_operator_page()
        body = response.body.decode("utf-8")
        self.assertIn("UNKNOWN — aucun incident autorisé", body)
        self.assertIn("NOT_ATTESTED", body)
        self.assertIn("SIM-GLPI", body)
        self.assertNotIn("TWIN_ACME_SIMULATED</td>", body)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])

    def test_rg_ux_03_client_requires_actor_and_tenant(self):
        js = (ROOT / "app/portal/noc_operator_client.js").read_text()
        for fence in ("tenant_acl_qualified !== true", "actor_identity_server_derived !== true",
                      "credentials: \"omit\"", "cache: \"no-store\"",
                      "redirect: \"error\"", "response.status === 503", "textContent"):
            self.assertIn(fence, js)
        self.assertNotIn("localStorage", js)
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("POST", js)

if __name__ == "__main__":
    unittest.main()
