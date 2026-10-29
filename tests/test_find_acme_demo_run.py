"""Offline, no-network contract tests for the read-only Core run locator."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "find_acme_demo_run", Path(__file__).resolve().parents[1] / "tools/find_acme_demo_run.py"
)
locator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(locator)


def fixtures():
    run = {"run_id": "RUN-ABC123", "incident_id": "INC-ABC123", "mode": "DEMO",
           "scenario_id": locator.SCENARIO, "status": "RESOLVED"}
    incident = {"incident_id": "INC-ABC123", "synthetic": True,
                "service_id": locator.SERVICE, "source": "synthetic-simulator"}
    detail = {"run": dict(run), "events": [
        {"event_type": "ANALYST_COMPLETED", "evidence_ids": ["EVD-1"]},
        {"event_type": "CRITIC_COMPLETED", "evidence_ids": ["EVD-1", "EVD-2"]}]}
    return run, incident, detail


class LocatorTests(unittest.TestCase):
    def make_get(self, run, incident, detail):
        def get(base, path):
            if path == "/api/runs": return {"items": [run]}
            if path == "/api/incidents?limit=500": return {"items": [incident]}
            if path == "/api/runs/RUN-ABC123": return detail
            raise AssertionError("unexpected endpoint: " + path)
        return get

    def test_real_registry_match_only(self):
        run, incident, detail = fixtures()
        result = locator.qualify("http://core", "http://portal", self.make_get(run, incident, detail))
        self.assertEqual(result["result"], "SOURCE_VERIFIED_REGISTRY_ONLY")
        self.assertEqual(result["run_id"], "RUN-ABC123")
        self.assertEqual(result["evidence_refs_unattested"], ["EVD-1", "EVD-2"])
        self.assertEqual(result["portal_url"], "http://portal/demo-studio/run/RUN-ABC123")
        self.assertEqual(result["timeline_url"], "http://portal/timeline?run_id=RUN-ABC123")
        self.assertEqual(result["payments_runtime_impact"], "UNKNOWN")
        self.assertFalse(result["e2e_attested"])

    def test_live_rejected(self):
        run, incident, _ = fixtures(); run["mode"] = "LIVE"
        self.assertEqual(locator.candidates({"items": [run]}, {"items": [incident]}), [])

    def test_fixture_not_core_incident(self):
        run, incident, _ = fixtures(); incident["incident_id"] = "INC-OTHER"
        self.assertEqual(locator.candidates({"items": [run]}, {"items": [incident]}), [])

    def test_non_synthetic_rejected(self):
        run, incident, _ = fixtures(); incident["synthetic"] = False
        self.assertEqual(locator.candidates({"items": [run]}, {"items": [incident]}), [])

    def test_wrong_service_rejected(self):
        run, incident, _ = fixtures(); incident["service_id"] = "ACME-SVC-ERP"
        self.assertEqual(locator.candidates({"items": [run]}, {"items": [incident]}), [])

    def test_wrong_scenario_rejected(self):
        run, incident, _ = fixtures(); run["scenario_id"] = "OTHER"
        self.assertEqual(locator.candidates({"items": [run]}, {"items": [incident]}), [])

    def test_untrusted_source_rejected(self):
        run, incident, _ = fixtures(); incident["source"] = "manual"
        self.assertEqual(locator.candidates({"items": [run]}, {"items": [incident]}), [])

    def test_untrusted_run_id_rejected(self):
        run, incident, _ = fixtures(); run["run_id"] = "../../unsafe"
        self.assertEqual(locator.candidates({"items": [run]}, {"items": [incident]}), [])

    def test_run_detail_mismatch_rejected(self):
        run, incident, detail = fixtures(); detail["run"]["scenario_id"] = "OTHER"
        result = locator.qualify("http://core", "http://portal", self.make_get(run, incident, detail))
        self.assertEqual(result["result"], "UNKNOWN")
        self.assertIsNone(result["run_id"])

    def test_no_matching_run(self):
        run, incident, detail = fixtures(); incident["synthetic"] = None
        result = locator.qualify("http://core", "http://portal", self.make_get(run, incident, detail))
        self.assertEqual(result["reason"], "NO_MATCHING_CORE_RUN")

    def test_missing_contract_fails_closed(self):
        with self.assertRaises(ValueError): locator.candidates({"runs": []}, {"items": []})

    def test_missing_events_fails_closed(self):
        run, incident, detail = fixtures(); detail.pop("events")
        result = locator.qualify("http://core", "http://portal", self.make_get(run, incident, detail))
        self.assertEqual(result["reason"], "RUN_DETAIL_MISMATCH")


if __name__ == "__main__":
    unittest.main()
