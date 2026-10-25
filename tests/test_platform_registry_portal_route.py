"""ASGI integration test for the static portal registry; synthetic/read-only only."""
from __future__ import annotations

import os
import pathlib
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

APP_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

# Import the real app with a synthetic-only internal token, never a real secret.
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "synthetic-ci-only-token", "AIOPS_ADMIN_TOKEN": ""}):
    from portal.main import app  # noqa: E402


class StaticPlatformRegistryPortalRouteTests(unittest.TestCase):
    def test_registry_route_is_mounted_once_on_existing_app(self):
        routes = [route for route in app.routes
                  if getattr(route, "path", None) == "/api/platform/components"]
        self.assertEqual(len(routes), 1)
        self.assertEqual(set(routes[0].methods or ()), {"GET"})

    def test_registry_route_returns_unknown_plan_with_no_runtime_claims(self):
        with TestClient(app) as client:
            response = client.get("/api/platform/components")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(response.headers["x-content-type-options"], "nosniff")
            self.assertEqual(response.headers["referrer-policy"], "no-referrer")

            payload = response.json()
            self.assertEqual(payload["schema"], "aiops-single-portal-component-registry-v1")
            self.assertEqual(payload["entrypoint"], "http://10.79.94.202:17777/")
            self.assertEqual(payload["source_mode"], "STATIC_REGISTRY_PLAN")
            self.assertEqual(payload["component_observation_source"], "ABSENT")
            self.assertIs(payload["route_mount_attested"], False)
            self.assertIs(payload["runtime_e2e_qualified"], False)
            self.assertIs(payload["production_qualified"], False)
            self.assertIs(payload["live_remediation_authorized"], False)
            self.assertEqual(payload["portal_route_presence_source"], "IN_PROCESS_ASGI_ROUTE_TABLE")
            self.assertEqual(payload["portal_route_presence_scope"], "EXACT_GET_PATH_ONLY")
            self.assertIs(payload["portal_route_presence_is_runtime_attestation"], False)
            actual_get_paths = {
                getattr(route, "path", None) for route in app.routes
                if "GET" in (getattr(route, "methods", None) or ())
            }
            items = payload["items"]
            self.assertEqual(len(items), 20)
            self.assertEqual(len({item["id"] for item in items}), 20)
            for item in items:
                with self.subTest(component=item["id"]):
                    self.assertEqual(item["state"], "UNKNOWN")
                    self.assertIsNone(item["observed_at"])
                    self.assertIs(item["route_mounted"], False)
                    self.assertIs(item["runtime_authenticated"], False)
                    self.assertIs(item["available_in_portal"], False)
                    self.assertIs(item["requires_route_integration"], True)
                    present = item["path"] in actual_get_paths
                    self.assertIs(item["portal_get_path_present"], present)
                    self.assertEqual(
                        item["portal_get_path_evidence"],
                        "EXACT_GET_PATH_MATCH" if present else "NO_EXACT_GET_PATH",
                    )

    def test_client_supplied_query_cannot_promote_health_or_attestation(self):
        with TestClient(app) as client:
            response = client.get(
                "/api/platform/components?state=OK&authenticated=true&runtime_authenticated=true"
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(row["state"] == "UNKNOWN" for row in response.json()["items"]))
        self.assertTrue(all(row["runtime_authenticated"] is False
                            for row in response.json()["items"]))
        self.assertIs(response.json()["route_mount_attested"], False)
        self.assertIs(response.json()["portal_route_presence_is_runtime_attestation"], False)
        expected_paths = {
            getattr(route, "path", None) for route in app.routes
            if "GET" in (getattr(route, "methods", None) or ())
        }
        self.assertTrue(all(row["portal_get_path_present"] == (row["path"] in expected_paths)
                            for row in response.json()["items"]))

    def test_non_get_method_is_not_exposed(self):
        with TestClient(app) as client:
            response = client.post("/api/platform/components", json={"state": "OK"})
        self.assertEqual(response.status_code, 405)



    def test_static_noc_convergence_page_is_mounted_once_and_read_only(self):
        routes = [route for route in app.routes
                  if getattr(route, "path", None) == "/noc"]
        self.assertEqual(len(routes), 1)
        self.assertEqual(set(routes[0].methods or ()), {"GET"})
        with TestClient(app) as client:
            response = client.get("/noc")
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/html", response.headers["content-type"])
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(response.headers["x-content-type-options"], "nosniff")
            self.assertEqual(response.headers["x-frame-options"], "DENY")
            self.assertIn("connect-src 'none'", response.headers["content-security-policy"])
            self.assertEqual(response.text.count('class="component-row"'), 20)
            registry = client.get("/api/platform/components").json()
            present_count = sum(1 for item in registry["items"] if item["portal_get_path_present"])
            self.assertEqual(
                response.text.count("<td>PRÉSENTE · GET (CHEMIN UNIQUEMENT)</td>"),
                present_count,
            )
            self.assertEqual(
                response.text.count("<td>ABSENTE · GET EXACT</td>"),
                20 - present_count,
            )
            self.assertIn("GET exact dans le code", response.text)
            self.assertIn("PLAN STATIQUE — PAS UN ÉCRAN NOC RUNTIME", response.text)
            self.assertIn("Qualification production : <code>NON</code>", response.text)

    def test_noc_page_shows_unknown_routes_without_forged_links_or_external_code(self):
        with TestClient(app) as client:
            response = client.get("/noc")
        body = response.text
        for label in ("Checkmk monitoring", "Thruk operations", "GLPI ITSM &amp; CMDB",
                      "n8n integration flows", "Grafana observability",
                      "Temporal orchestration", "DGX Analyst &amp; Critic"):
            with self.subTest(label=label):
                self.assertIn(label, body)
        self.assertEqual(body.count("<strong>INCONNU</strong>"), 20)
        self.assertEqual(body.count("<td>ABSENTE</td>"), 20)
        self.assertEqual(body.count("<td>NON · À INTÉGRER</td>"), 20)
        self.assertEqual(body.count("<td>NON</td>"), 20)
        self.assertNotIn("<a ", body.lower())
        self.assertNotIn("<script", body.lower())
        self.assertNotIn("<form", body.lower())
        self.assertNotIn("fetch(", body.lower())
        self.assertIn("Cette page est servie localement par le portail existant", body)

    def test_noc_inventory_rejects_non_get_methods(self):
        with TestClient(app) as client:
            response = client.post("/noc", json={"state": "OK", "authenticated": True})
        self.assertEqual(response.status_code, 405)

if __name__ == "__main__":
    unittest.main()
