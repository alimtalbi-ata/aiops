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

    def test_rg_ux_10_source_backed_reference_is_separate_from_incident_queue(self):
        # Reuse the exact existing six-CI fixture, not a fabricated PG16 9/8
        # topology or an authorized NOC incident.
        module = importlib.import_module("portal.noc_operator_page")
        impact = importlib.import_module("portal.acme_impact_read_model")
        model = impact.build_acme_impact_read_model()
        with patch("shared.http.get_json", side_effect=AssertionError("no upstream read")), \
             patch("shared.http.post_json", side_effect=AssertionError("no upstream write")):
            page = module.noc_operator_page()
        body = page.body.decode("utf-8")
        for marker in ("SYNTHETIC_REFERENCE_ONLY", "LOCAL_SYNTHETIC_FIXTURE",
                       model["source_sha256"], "SAN-FABRIC-A", "APP-PAY-01",
                       "9 nœuds / 8 arêtes", 'href="/demo/acme-impact"'):
            self.assertIn(marker, body)
        self.assertIn("UNKNOWN — aucun incident autorisé", body)
        self.assertIn("Analyst/Critic : NOT_ATTESTED", body)
        self.assertNotIn("runtime_attested=true", body)
        self.assertEqual(page.headers["cache-control"], "no-store")

    def test_rg_ux_11_invalid_fixture_fails_closed_without_leaking_source(self):
        module = importlib.import_module("portal.noc_operator_page")
        for outcome in (ValueError("private_fixture_path"),
                        {"schema": "aiops.synthetic-impact-read-model.v1",
                         "provenance": "SIMULATED_TARGET",
                         "runtime_attested": True,
                         "source_sha256": "PRIVATE_FORGED_SHA"}):
            with self.subTest(outcome=type(outcome).__name__):
                kwargs = ({"side_effect": outcome} if isinstance(outcome, Exception)
                          else {"return_value": outcome})
                with patch.object(module, "build_acme_impact_read_model", **kwargs):
                    body = module.noc_operator_page().body.decode("utf-8")
                self.assertIn("UNKNOWN — fixture locale absente ou invalide", body)
                self.assertIn("UNKNOWN — aucun incident autorisé", body)
                self.assertNotIn("PRIVATE_FORGED_SHA", body)
                self.assertNotIn("private_fixture_path", body)
                self.assertNotIn("SYNTHETIC_REFERENCE_ONLY", body)

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
