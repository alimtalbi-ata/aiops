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
        {"stage": "INGEST", "event_type": "RUN_CREATED", "status": "CREATED",
         "payload": {"scenario_id": locator.SCENARIO, "mode": "DEMO"}},
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

    def test_pinned_operator_pair_matches_only_exact_run_and_incident(self):
        run, incident, detail = fixtures()
        result = locator.qualify(
            "http://core", "http://portal", self.make_get(run, incident, detail),
            expected_run_id="RUN-ABC123", expected_incident_id="INC-ABC123")
        self.assertEqual(result["result"], "SOURCE_VERIFIED_REGISTRY_ONLY")
        self.assertTrue(result["operator_pair_pinned"])
        self.assertEqual(result["incident_id"], "INC-ABC123")

    def test_pinned_operator_pair_wrong_incident_fails_closed(self):
        run, incident, detail = fixtures()
        result = locator.qualify(
            "http://core", "http://portal", self.make_get(run, incident, detail),
            expected_run_id="RUN-ABC123", expected_incident_id="INC-OTHER")
        self.assertEqual(result["reason"], "EXPECTED_PAIR_NOT_QUALIFIED_IN_REGISTRY_WINDOW")
        self.assertIsNone(result["run_id"])

    def test_pinned_operator_pair_wrong_run_fails_closed(self):
        run, incident, detail = fixtures()
        result = locator.qualify(
            "http://core", "http://portal", self.make_get(run, incident, detail),
            expected_run_id="RUN-OTHER", expected_incident_id="INC-ABC123")
        self.assertEqual(result["reason"], "EXPECTED_PAIR_NOT_QUALIFIED_IN_REGISTRY_WINDOW")
        self.assertIsNone(result["run_id"])

    def test_pinned_operator_pair_incomplete_or_invalid_fails_closed(self):
        run, incident, detail = fixtures()
        get = self.make_get(run, incident, detail)
        for expected_run_id, expected_incident_id, reason in (
            ("RUN-ABC123", None, "EXPECTED_PAIR_INCOMPLETE"),
            (None, "INC-ABC123", "EXPECTED_PAIR_INCOMPLETE"),
            ("../../bad", "INC-ABC123", "EXPECTED_PAIR_INVALID"),
            ("RUN-ABC123", ["INC-ABC123"], "EXPECTED_PAIR_INVALID"),
            ("RUN-ABC123", "", "EXPECTED_PAIR_INVALID"),
        ):
            with self.subTest(run=expected_run_id, incident=expected_incident_id):
                result = locator.qualify(
                    "http://core", "http://portal", get,
                    expected_run_id=expected_run_id,
                    expected_incident_id=expected_incident_id)
                self.assertEqual(result["reason"], reason)
                self.assertIsNone(result["run_id"])

    def test_pinned_operator_pair_rejects_stale_detail(self):
        run, incident, detail = fixtures()
        detail["run"]["incident_id"] = "INC-OTHER"
        result = locator.qualify(
            "http://core", "http://portal", self.make_get(run, incident, detail),
            expected_run_id="RUN-ABC123", expected_incident_id="INC-ABC123")
        self.assertEqual(result["reason"], "RUN_DETAIL_MISMATCH")
        self.assertIsNone(result["run_id"])

    def test_live_rejected(self):
        run, incident, _ = fixtures(); run["mode"] = "LIVE"
        self.assertEqual(locator.candidates({"items": [run]}, {"items": [incident]}), [])

    def test_replay_and_story_not_mislabeled_as_demo(self):
        for mode in ("REPLAY", "STORY"):
            with self.subTest(mode=mode):
                run, incident, detail = fixtures()
                run["mode"] = mode
                detail["run"]["mode"] = mode
                detail["events"][0]["payload"]["mode"] = mode
                self.assertEqual(
                    locator.candidates({"items": [run]}, {"items": [incident]}), [])
                result = locator.qualify(
                    "http://core", "http://portal", self.make_get(run, incident, detail),
                    expected_run_id="RUN-ABC123", expected_incident_id="INC-ABC123")
                self.assertEqual(result["result"], "UNKNOWN")
                self.assertEqual(result["reason"], "EXPECTED_PAIR_NOT_QUALIFIED_IN_REGISTRY_WINDOW")
                self.assertIsNone(result["run_id"])

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

    def test_unhashable_incident_reference_fails_closed(self):
        run, incident, detail = fixtures()
        for bad in ([], {}, ["INC-ABC123"], {"id": "INC-ABC123"}):
            with self.subTest(incident_id=bad):
                run["incident_id"] = bad
                result = locator.qualify("http://core", "http://portal",
                                         self.make_get(run, incident, detail))
                self.assertEqual(result, {"result": "UNKNOWN",
                                          "reason": "REGISTRY_CONTRACT_MISMATCH",
                                          "run_id": None})

    def test_empty_or_invalid_incident_reference_fails_closed(self):
        run, incident, detail = fixtures()
        for bad in (None, 42, False, ""):
            with self.subTest(incident_id=bad):
                run["incident_id"] = bad
                result = locator.qualify("http://core", "http://portal",
                                         self.make_get(run, incident, detail))
                self.assertEqual(result, {"result": "UNKNOWN",
                                          "reason": "REGISTRY_CONTRACT_MISMATCH",
                                          "run_id": None})

    def test_duplicate_incident_id_fails_closed(self):
        run, incident, detail = fixtures()
        original = self.make_get(run, incident, detail)

        def get(base, path):
            if path == "/api/incidents?limit=500":
                return {"items": [incident, dict(incident, source="manual")]}
            return original(base, path)

        result = locator.qualify("http://core", "http://portal", get)
        self.assertEqual(result, {"result": "UNKNOWN",
                                  "reason": "REGISTRY_CONTRACT_MISMATCH", "run_id": None})

    def test_duplicate_run_id_fails_closed(self):
        run, incident, detail = fixtures()
        original = self.make_get(run, incident, detail)

        def get(base, path):
            if path == "/api/runs":
                return {"items": [run, dict(run, mode="LIVE")]}
            return original(base, path)

        result = locator.qualify("http://core", "http://portal", get)
        self.assertEqual(result["reason"], "REGISTRY_CONTRACT_MISMATCH")
        self.assertIsNone(result["run_id"])

    def test_run_detail_status_drift_rejected(self):
        run, incident, detail = fixtures()
        detail["run"]["status"] = "RUNNING"
        result = locator.qualify("http://core", "http://portal",
                                 self.make_get(run, incident, detail))
        self.assertEqual(result["reason"], "RUN_DETAIL_MISMATCH")
        self.assertIsNone(result["run_id"])

    def test_run_detail_missing_status_rejected(self):
        run, incident, detail = fixtures()
        detail["run"].pop("status")
        result = locator.qualify("http://core", "http://portal",
                                 self.make_get(run, incident, detail))
        self.assertEqual(result["reason"], "RUN_DETAIL_MISMATCH")
        self.assertIsNone(result["run_id"])

    def test_no_matching_run(self):
        run, incident, detail = fixtures(); incident["synthetic"] = None
        result = locator.qualify("http://core", "http://portal", self.make_get(run, incident, detail))
        self.assertEqual(result["reason"], "NO_MATCHING_CORE_RUN")

    def test_missing_contract_fails_closed(self):
        with self.assertRaises(ValueError): locator.candidates({"runs": []}, {"items": []})

    def test_missing_run_created_event_fails_closed(self):
        run, incident, detail = fixtures()
        detail["events"] = [e for e in detail["events"]
                            if e.get("event_type") != "RUN_CREATED"]
        result = locator.qualify("http://core", "http://portal",
                                 self.make_get(run, incident, detail))
        self.assertEqual(result["reason"], "RUN_DETAIL_MISMATCH")
        self.assertIsNone(result["run_id"])

    def test_run_created_wrong_scenario_or_mode_fails_closed(self):
        for key, bad in (("scenario_id", "OTHER"), ("mode", "LIVE")):
            with self.subTest(key=key):
                run, incident, detail = fixtures()
                detail["events"][0]["payload"][key] = bad
                result = locator.qualify("http://core", "http://portal",
                                         self.make_get(run, incident, detail))
                self.assertEqual(result["reason"], "RUN_DETAIL_MISMATCH")
                self.assertIsNone(result["run_id"])

    def test_duplicate_or_malformed_run_created_event_fails_closed(self):
        for mutation in ("duplicate", "missing_payload", "wrong_stage", "wrong_status"):
            with self.subTest(mutation=mutation):
                run, incident, detail = fixtures()
                event = detail["events"][0]
                if mutation == "duplicate":
                    detail["events"].append(dict(event))
                elif mutation == "missing_payload":
                    event.pop("payload")
                elif mutation == "wrong_stage":
                    event["stage"] = "RUN"
                else:
                    event["status"] = "RESOLVED"
                result = locator.qualify("http://core", "http://portal",
                                         self.make_get(run, incident, detail))
                self.assertEqual(result["reason"], "RUN_DETAIL_MISMATCH")
                self.assertIsNone(result["run_id"])

    def test_missing_events_fails_closed(self):
        run, incident, detail = fixtures(); detail.pop("events")
        result = locator.qualify("http://core", "http://portal", self.make_get(run, incident, detail))
        self.assertEqual(result["reason"], "RUN_DETAIL_MISMATCH")


    def test_run_window_full_is_not_proof_of_absence(self):
        def get(base, path):
            if path == "/api/runs":
                return {"items": [{"run_id": f"RUN-{i}", "scenario_id": "OTHER", "mode": "DEMO"} for i in range(100)]}
            if path == "/api/incidents?limit=500": return {"items": []}
            raise AssertionError(path)
        result = locator.qualify("http://core", "http://portal", get)
        self.assertEqual(result, {"result": "UNKNOWN", "reason": "REGISTRY_WINDOW_LIMITED", "run_id": None})

    def test_incident_window_full_is_not_proof_of_absence(self):
        def get(base, path):
            if path == "/api/runs": return {"items": []}
            if path == "/api/incidents?limit=500":
                return {"items": [{"incident_id": f"INC-{i}"} for i in range(500)]}
            raise AssertionError(path)
        result = locator.qualify("http://core", "http://portal", get)
        self.assertEqual(result["reason"], "REGISTRY_WINDOW_LIMITED")


if __name__ == "__main__":
    unittest.main()
