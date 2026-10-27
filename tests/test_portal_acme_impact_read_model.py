"""ASGI tests for the local ACME impact view; no backend, DB or live actions."""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

APP_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "synthetic-ci-only-token", "AIOPS_ADMIN_TOKEN": ""}):
    from portal.main import app  # noqa: E402
from portal import acme_impact_read_model as impact  # noqa: E402
from portal.ui_theme import NAV, shell  # noqa: E402


class AcmeImpactPortalReadModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_routes_are_mounted_once_as_get_on_existing_portal(self):
        expected = {
            "/api/demo/acme-impact": "synthetic_acme_impact_read_model",
            "/demo/acme-impact": "synthetic_acme_impact_page",
        }
        for path, name in expected.items():
            routes = [r for r in app.routes if getattr(r, "path", None) == path]
            with self.subTest(path=path):
                self.assertEqual(len(routes), 1)
                self.assertEqual(set(routes[0].methods or ()), {"GET"})
                self.assertEqual(routes[0].name, name)

    def test_existing_portal_navigation_exposes_noc_plan_and_acme_simulation(self):
        paths = [path for path, _label in NAV]
        self.assertEqual(paths.count("/noc"), 1)
        self.assertEqual(paths.count("/demo/acme-impact"), 1)
        page = shell("/", "Cockpit", "Synthetic test", "<p>fixture</p>")
        self.assertIn('href="/noc"', page)
        self.assertIn('href="/demo/acme-impact"', page)
        self.assertIn("NOC (plan)", page)
        self.assertIn("Impact ACME (SIM)", page)

    def test_fixture_and_validator_are_packaged_inside_portal_directory(self):
        expected = pathlib.Path(impact.__file__).resolve().with_name("acme-fixtures.json")
        self.assertEqual(impact.FIXTURE_PATH.resolve(), expected)
        self.assertTrue(expected.is_file())
        self.assertNotIn("/demo/integrations/", str(impact.FIXTURE_PATH))
        model = impact.build_acme_impact_read_model()
        self.assertEqual(model["source_sha256"], hashlib.sha256(expected.read_bytes()).hexdigest())
        self.assertEqual(model["source_artifact"], "app/portal/acme-fixtures.json")
        self.assertEqual(model["provenance"], "SIMULATED_TARGET")
        self.assertIs(model["runtime_attested"], False)
        self.assertIs(model["live_remediation_authorized"], False)

    def test_json_model_is_deterministic_and_hash_binds_exact_bytes(self):
        raw = impact.FIXTURE_PATH.read_bytes()
        expected_sha = hashlib.sha256(raw).hexdigest()
        first = self.client.get("/api/demo/acme-impact")
        second = self.client.get("/api/demo/acme-impact")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json(), second.json())
        model = first.json()
        self.assertEqual(model["schema"], "aiops.synthetic-impact-read-model.v1")
        self.assertEqual(model["run_id"], "SIM-ACME-" + expected_sha[:16].upper())
        self.assertEqual(model["source_sha256"], expected_sha)
        self.assertEqual(model["incident_id"], "ACME-DEMO-SAN-001")
        self.assertEqual(model["impact_incident_id"], "ACME-DEMO-PAY-002")
        self.assertEqual(
            model["impact_path"],
            ["SAN-FABRIC-A", "HOST-ESX-01", "VM-PAY-01", "APP-PAY-01"],
        )
        self.assertIsNone(model["ticket_id"])
        self.assertEqual(model["ticket_id_provenance"], "ABSENT_NO_GLPI_WRITE")
        self.assertIsNone(model["event_timestamp_utc"])
        self.assertEqual(model["timestamp_provenance"], "ABSENT_NO_RUNTIME_EVENT")
        self.assertEqual(model["provenance"], "SIMULATED_TARGET")
        self.assertIs(model["runtime_evidence_present"], False)
        self.assertIs(model["runtime_attested"], False)
        self.assertIs(model["production_qualified"], False)
        self.assertIs(model["live_remediation_authorized"], False)
        self.assertEqual(first.headers["cache-control"], "no-store")
        self.assertEqual(first.headers["x-content-type-options"], "nosniff")

    def test_html_snapshot_is_local_and_has_no_links_scripts_or_forms(self):
        response = self.client.get("/demo/acme-impact")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("ACME — SAN P1", response.text)
        self.assertIn("background:#0b1220", response.text)
        self.assertIn("style-src", response.headers["content-security-policy"])
        self.assertIn("Payments P2", response.text)
        self.assertIn("<svg ", response.text)
        self.assertIn('aria-label="Dépendances SAN vers application Payments, simulation"', response.text)
        self.assertIn("SAN-FABRIC-A", response.text)
        self.assertIn("HOST-ESX-01", response.text)
        self.assertIn("APP-PAY-01", response.text)
        self.assertIn("LOCAL_SYNTHETIC_DEPENDENCY_GRAPH", response.text)
        self.assertIn("ABSENT_NO_GLPI_WRITE", response.text)
        self.assertIn("ABSENT_NO_RUNTIME_EVENT", response.text)
        self.assertIn(impact.build_acme_impact_read_model()["source_sha256"], response.text)
        self.assertNotIn("<script", response.text.lower())
        self.assertNotIn("<form", response.text.lower())
        self.assertNotIn("<a ", response.text.lower())
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("connect-src 'none'", response.headers["content-security-policy"])

    def test_html_escapes_values_even_if_a_future_fixture_contains_markup(self):
        model = impact.build_acme_impact_read_model()
        model["run_id"] = "<script>alert(1)</script>"
        model["impact_path"] = ["<img src=x onerror=alert(1)>"]
        with patch.object(impact, "build_acme_impact_read_model", return_value=model):
            response = self.client.get("/demo/acme-impact")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("<script", response.text.lower())
        self.assertNotIn("<img", response.text.lower())
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", response.text)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", response.text)

    def test_invalid_or_missing_fixture_fails_closed_with_no_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            invalid_path = pathlib.Path(tmp) / "invalid.json"
            invalid = json.loads(impact.FIXTURE_PATH.read_text(encoding="utf-8"))
            invalid["provenance"] = "OBSERVED_RUNTIME"
            invalid_path.write_text(json.dumps(invalid), encoding="utf-8")
            with patch.object(impact, "FIXTURE_PATH", invalid_path):
                rejected = self.client.get("/api/demo/acme-impact")
                self.assertEqual(rejected.status_code, 503)
                self.assertEqual(
                    rejected.json()["detail"],
                    "synthetic_impact_fixture_unavailable_or_invalid",
                )
            invalid["provenance"] = "SIMULATED_TARGET"
            invalid["incidents"][0]["severity"] = []
            malformed_path = pathlib.Path(tmp) / "malformed-severity.json"
            malformed_path.write_text(json.dumps(invalid), encoding="utf-8")
            with patch.object(impact, "FIXTURE_PATH", malformed_path):
                malformed = self.client.get("/api/demo/acme-impact")
                self.assertEqual(malformed.status_code, 503)
                self.assertEqual(
                    malformed.json()["detail"],
                    "synthetic_impact_fixture_unavailable_or_invalid",
                )

            missing_path = pathlib.Path(tmp) / "missing.json"
            with patch.object(impact, "FIXTURE_PATH", missing_path):
                missing = self.client.get("/api/demo/acme-impact")
                self.assertEqual(missing.status_code, 503)
                self.assertEqual(
                    missing.json()["detail"],
                    "synthetic_impact_fixture_unavailable_or_invalid",
                )

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "requires POSIX O_NOFOLLOW")
    def test_symlink_fixture_is_rejected_without_disclosing_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            target = root / "valid.json"
            target.write_bytes(impact.FIXTURE_PATH.read_bytes())
            link = root / "fixture.json"
            link.symlink_to(target)
            with patch.object(impact, "FIXTURE_PATH", link):
                response = self.client.get("/api/demo/acme-impact")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(
                response.json(),
                {"detail": "synthetic_impact_fixture_unavailable_or_invalid"},
            )

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "requires POSIX O_NOFOLLOW")
    def test_oversized_fixture_is_rejected_before_json_parsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "oversized.json"
            path.write_bytes(b" " * (impact.MAX_FIXTURE_BYTES + 1))
            with patch.object(impact, "FIXTURE_PATH", path):
                response = self.client.get("/api/demo/acme-impact")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(
                response.json(),
                {"detail": "synthetic_impact_fixture_unavailable_or_invalid"},
            )

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW") and hasattr(os, "mkfifo"), "requires POSIX FIFO support")
    def test_non_regular_fixture_is_rejected_without_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            fifo = pathlib.Path(tmp) / "fixture.json"
            os.mkfifo(fifo)
            with patch.object(impact, "FIXTURE_PATH", fifo):
                response = self.client.get("/api/demo/acme-impact")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(
                response.json(),
                {"detail": "synthetic_impact_fixture_unavailable_or_invalid"},
            )

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "requires POSIX O_NOFOLLOW")
    def test_fixture_mutation_during_read_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "fixture.json"
            path.write_bytes(impact.FIXTURE_PATH.read_bytes())
            real_fstat = os.fstat
            calls = 0

            def mutate_after_initial_stat(fd):
                nonlocal calls
                result = real_fstat(fd)
                calls += 1
                if calls == 1:
                    path.write_bytes(b"{}")
                return result

            with patch.object(impact, "FIXTURE_PATH", path):
                with patch.object(impact.os, "fstat", side_effect=mutate_after_initial_stat):
                    response = self.client.get("/api/demo/acme-impact")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(
                response.json(),
                {"detail": "synthetic_impact_fixture_unavailable_or_invalid"},
            )

    def test_mutating_methods_are_not_exposed(self):
        self.assertEqual(self.client.post("/api/demo/acme-impact").status_code, 405)
        self.assertEqual(self.client.post("/demo/acme-impact").status_code, 405)


if __name__ == "__main__":
    unittest.main()
