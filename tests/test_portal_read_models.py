"""Pure unit tests for read-model failure semantics; no integration service mocked as LIVE."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.portal_read_models import read_portal_snapshot


class PortalReadModelTests(unittest.TestCase):
    def test_valid_read_models_remain_unattested(self):
        responses = {
            "/api/dashboard": {"open_p1": 1, "open_incidents": 2, "running": 0,
                               "blocked": 1, "twin_nodes": 4, "degraded_nodes": 1},
            "/api/runs": {"items": [{"run_id": "RUN-1", "mode": "DEMO", "status": "BLOCKED"}]},
            "/api/twin/summary": {"nodes": 4, "edges": 3},
        }
        result = read_portal_snapshot(lambda base, path: responses[path], "core", "twin")
        self.assertEqual(set(result["states"].values()), {"READABLE_UNVERIFIED"})
        self.assertEqual(result["runs"]["items"][0]["run_id"], "RUN-1")
        self.assertFalse(result["runtime_authenticated"])
        self.assertFalse(result["live_remediation_authorized"])

    def test_down_upstreams_are_unknown_not_empty(self):
        def failed(base, path):
            raise TimeoutError("unreachable")
        result = read_portal_snapshot(failed, "core", "twin")
        self.assertEqual(set(result["states"].values()), {"UNKNOWN"})
        for key in ("dashboard", "runs", "twin"):
            self.assertIsNone(result[key])

    def test_partial_failure_does_not_erase_good_read_models(self):
        def fetch(base, path):
            if path == "/api/dashboard":
                return {"open_p1": 0, "open_incidents": 0, "running": 0,
                        "blocked": 0, "twin_nodes": 0, "degraded_nodes": 0}
            raise ConnectionError("unavailable")
        result = read_portal_snapshot(fetch, "core", "twin")
        self.assertEqual(result["states"]["dashboard"], "READABLE_UNVERIFIED")
        self.assertEqual(result["states"]["runs"], "UNKNOWN")
        self.assertEqual(result["states"]["twin"], "UNKNOWN")

    def test_malformed_payload_is_unknown(self):
        for bad in (None, {}, [], {"items": "not a list"}, {"items": [{"run_id": None}]}):
            with self.subTest(bad=bad):
                result = read_portal_snapshot(lambda base, path: bad, "core", "twin")
                self.assertEqual(set(result["states"].values()), {"UNKNOWN"})

    def test_boolean_counters_not_accepted(self):
        def fetch(base, path):
            if path == "/api/dashboard":
                return {"open_p1": True, "open_incidents": 0, "running": 0,
                        "blocked": 0, "twin_nodes": 0, "degraded_nodes": 0}
            return {}
        result = read_portal_snapshot(fetch, "core", "twin")
        self.assertIsNone(result["dashboard"])
        self.assertEqual(result["states"]["dashboard"], "UNKNOWN")

    def test_unqualified_tenant_run_claims_fail_closed_without_leak(self):
        # A read token is not an independently verified tenant/actor ACL.
        # Test nested and differently cased claims, even when values are null.
        for scoped in (
            {"tenant_id": "secret-tenant"},
            {"tenantId": None},
            {"organizationId": "secret-tenant"},
            {"metadata": {"workspace_id": "secret-tenant"}},
            {"evidence": [{"account-id": "secret-tenant"}]},
            {"tenant_acl_qualified": True},
        ):
            with self.subTest(scoped=scoped):
                def fetch(base, path):
                    if path == "/api/runs":
                        return {"items": [{"run_id": "RUN-1", "mode": "DEMO",
                                           "status": "BLOCKED", **scoped}]}
                    if path == "/api/dashboard":
                        return {"open_p1": 0, "open_incidents": 0, "running": 0,
                                "blocked": 0, "twin_nodes": 0, "degraded_nodes": 0}
                    return {"nodes": 0, "edges": 0}
                result = read_portal_snapshot(fetch, "core", "twin")
                self.assertIsNone(result["runs"])
                self.assertEqual(result["states"]["runs"], "UNKNOWN")
                self.assertEqual(result["states"]["dashboard"], "READABLE_UNVERIFIED")
                self.assertFalse(result["tenant_acl_qualified"])
                self.assertNotIn("secret-tenant", str(result))

    def test_tenant_claim_in_inventory_root_is_rejected(self):
        def fetch(base, path):
            return ({"items": [{"run_id": "RUN-1"}],
                     "tenant_scope": {"tenant_id": "secret-tenant"}}
                    if path == "/api/runs" else {})
        result = read_portal_snapshot(fetch, "core", "twin")
        self.assertIsNone(result["runs"])
        self.assertNotIn("secret-tenant", str(result))

    def test_deep_uninspectable_run_payload_fails_closed(self):
        nested = {"safe": "leaf"}
        for _ in range(10):
            nested = {"meta": nested}
        result = read_portal_snapshot(
            lambda base, path: {"items": [{"run_id": "RUN-1", "details": nested}]}
            if path == "/api/runs" else {}, "core", "twin")
        self.assertIsNone(result["runs"])
        self.assertEqual(result["states"]["runs"], "UNKNOWN")

    def test_portal_bootstrap_does_not_expose_tenant_scoped_run(self):
        # No runtime services are contacted; this tests portal response wiring.
        def fetch(base, path):
            return ({"items": [{"run_id": "RUN-SECRET", "tenant_id": "secret-tenant"}]}
                    if path == "/api/runs" else {})
        snapshot = read_portal_snapshot(fetch, "core", "twin")
        with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "synthetic-ci-only-token"}):
            from portal import main as portal_main
        with patch.object(portal_main, "read_portal_snapshot", return_value=snapshot):
            response = portal_main.bootstrap()
            homepage = portal_main.home()
        self.assertNotIn(b"secret-tenant", response.body)
        self.assertNotIn(b"RUN-SECRET", response.body)
        self.assertNotIn("secret-tenant", homepage)
        self.assertNotIn("RUN-SECRET", homepage)
        self.assertIn("UNKNOWN", homepage)

    def test_never_contacts_unconfigured_service(self):
        calls = []
        def fetch(base, path):
            calls.append((base, path))
            raise OSError("not running")
        read_portal_snapshot(fetch, "core", "twin")
        self.assertEqual(calls, [("core", "/api/dashboard"), ("core", "/api/runs"),
                                 ("twin", "/api/twin/summary")])


if __name__ == "__main__":
    unittest.main()
