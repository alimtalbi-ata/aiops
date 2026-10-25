"""ASGI integration test for the static portal registry; synthetic/read-only only."""
from __future__ import annotations

import pathlib
import sys
import unittest

from fastapi.testclient import TestClient

APP_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

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

    def test_non_get_method_is_not_exposed(self):
        with TestClient(app) as client:
            response = client.post("/api/platform/components", json={"state": "OK"})
        self.assertEqual(response.status_code, 405)


if __name__ == "__main__":
    unittest.main()
