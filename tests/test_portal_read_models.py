"""Pure unit tests for read-model failure semantics; no integration service mocked as LIVE."""
import sys
import unittest
from pathlib import Path

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

    def test_never_contacts_unconfigured_service(self):
        calls = []
        def fetch(base, path):
            calls.append((base, path))
            raise OSError("not running")
        read_portal_snapshot(fetch, "core", "twin")
        self.assertEqual(calls, [("core", "/api/dashboard"), ("core", "/api/runs"),
                                 ("twin", "/api/twin/summary")])


    def test_upstream_extra_fields_are_not_forwarded_to_browser(self):
        responses = {
            "/api/dashboard": {"open_p1": 1, "open_incidents": 2, "running": 0,
                               "blocked": 0, "twin_nodes": 4, "degraded_nodes": 0,
                               "internal_token": "DO-NOT-LEAK"},
            "/api/runs": {"items": [{"run_id": "R-1", "mode": "LIVE",
                                    "status": "BLOCKED", "overall_confidence": 0.5,
                                    "scenario_id": "SCN-1", "evidence_payload": "DO-NOT-LEAK",
                                    "live_remediation_authorized": True}],
                          "admin_token": "DO-NOT-LEAK"},
            "/api/twin/summary": {"nodes": 4, "edges": 2,
                                  "nodes_by_type": {"switch": 4},
                                  "states": {"DEGRADED": 1},
                                  "secret": "DO-NOT-LEAK"},
        }
        result = read_portal_snapshot(lambda base, path: responses[path], "core", "twin")
        self.assertEqual(set(result["states"].values()), {"READABLE_UNVERIFIED"})
        self.assertNotIn("DO-NOT-LEAK", str(result))
        self.assertNotIn("live_remediation_authorized", result["runs"]["items"][0])
        self.assertEqual(result["runs"]["items"][0]["mode"], "LIVE")
        self.assertFalse(result["live_remediation_authorized"])
        self.assertFalse(result["runtime_authenticated"])
        self.assertEqual(result["twin"]["nodes_by_type"], {"switch": 4})

    def test_invalid_optional_run_fields_fail_closed(self):
        bad_rows = (
            {"run_id": "R-1", "status": {"unsafe": "nested"}},
            {"run_id": "R-1", "mode": ["DEMO"]},
            {"run_id": "R-1", "overall_confidence": True},
            {"run_id": "R-1", "overall_confidence": float("nan")},
            {"run_id": "R-1", "overall_confidence": 1.5},
            {"run_id": "R-1", "scenario_id": "X" * 257},
            {"run_id": "R-1", "status": "PASS\\r\\nInjected: true"},
            {"run_id": ""},
        )
        for row in bad_rows:
            with self.subTest(row=row):
                result = read_portal_snapshot(
                    lambda base, path: {"items": [row]} if path == "/api/runs" else {},
                    "core", "twin")
                self.assertEqual(result["states"]["runs"], "UNKNOWN")
                self.assertIsNone(result["runs"])

    def test_duplicate_run_ids_fail_closed(self):
        result = read_portal_snapshot(
            lambda base, path: {"items": [{"run_id": "R-1"}, {"run_id": "R-1"}]}
            if path == "/api/runs" else {}, "core", "twin")
        self.assertEqual(result["states"]["runs"], "UNKNOWN")
        self.assertIsNone(result["runs"])

    def test_twin_breakdown_malformed_is_unknown(self):
        for value in ({"SWITCH": True}, {"SWITCH": -1}, ["SWITCH"],
                      {"": 1}, {"X" * 257: 1}):
            with self.subTest(value=value):
                result = read_portal_snapshot(
                    lambda base, path: {"nodes": 1, "edges": 0, "states": value}
                    if path == "/api/twin/summary" else {}, "core", "twin")
                self.assertEqual(result["states"]["twin"], "UNKNOWN")
                self.assertIsNone(result["twin"])

    def test_empty_run_inventory_is_readable_not_proof_of_health(self):
        result = read_portal_snapshot(
            lambda base, path: {"items": []} if path == "/api/runs" else {},
            "core", "twin")
        self.assertEqual(result["states"]["runs"], "READABLE_UNVERIFIED")
        self.assertEqual(result["runs"], {"items": []})
        self.assertFalse(result["runtime_authenticated"])


if __name__ == "__main__":
    unittest.main()
