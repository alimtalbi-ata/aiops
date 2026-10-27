import copy
import json
import tempfile
import unittest
from pathlib import Path
from demo.star_legacy_replay_adapter import build_replay
from demo.star_legacy_portal_binding import bind_replay_to_transport, export_legacy_portal_binding
from demo.star_snapshot_choreography import CUES

RUN_ID = "RUN-STAR-LEGACY-001"


def sample():
    run = {"run": {"run_id": RUN_ID, "mode": "DEMO", "status": "RESOLVED"},
           "events": [{"timestamp": "2026-10-23T18:00:00Z", "evidence_ids": [], "private": "DO_NOT_EXPORT"}],
           "stages": [{"timestamp": "2026-10-23T18:00:01Z"}]}
    ledger = {"run_id": RUN_ID, "analyses": [{"timestamp": "2026-10-23T18:00:02Z"}],
              "critiques": [{"timestamp": "2026-10-23T18:00:03Z"}],
              "policy_decisions": [{"timestamp": "2026-10-23T18:00:04Z"}]}
    evidence = {"run_id": RUN_ID, "items": []}
    transport = {"schema": "star-portal-transport-v1", "run_id": RUN_ID,
                 "scenario": "SAN_FABRIC_P1", "frames": [{
                     "step": cue.cue, "application": cue.service,
                     "expected_view": cue.view, "expected_state": cue.required_state,
                     "capture_status": "missing", "runtime_verified": False,
                     "action_allowed": False} for cue in CUES],
                 "safety": {"read_only": True, "runtime_authenticated": False,
                            "portal_integration_qualified": False, "remediation_authorized": False}}
    return transport, build_replay(run, ledger, evidence)


class LegacyPortalBindingTests(unittest.TestCase):
    def test_explicit_bindings_and_missing_cues(self):
        transport, replay = sample()
        doc = bind_replay_to_transport(transport, replay, {
            "detect": {"source": "events", "source_index": 1},
            "analyze": {"source": "analyses", "source_index": 1},
            "approve": {"source": "policy_decisions", "source_index": 1}})
        self.assertEqual(len(doc["bindings"]), 9)
        self.assertEqual(doc["bindings"][0]["binding_status"], "operator_declared_unattested")
        self.assertEqual(doc["bindings"][1]["binding_status"], "unbound")
        self.assertFalse(doc["safety"]["portal_integration_qualified"])
        self.assertNotIn("DO_NOT_EXPORT", json.dumps(doc))
        self.assertEqual(doc, bind_replay_to_transport(copy.deepcopy(transport), copy.deepcopy(replay), {
            "detect": {"source": "events", "source_index": 1},
            "analyze": {"source": "analyses", "source_index": 1},
            "approve": {"source": "policy_decisions", "source_index": 1}}))

    def test_identity_mismatch_rejected(self):
        t, r = sample()
        t["run_id"] = "RUN-OTHER"
        with self.assertRaises(ValueError): bind_replay_to_transport(t, r, {})

    def test_wrong_source_family_rejected(self):
        t, r = sample()
        with self.assertRaises(ValueError): bind_replay_to_transport(t, r, {"detect": {"source": "policy_decisions", "source_index": 1}})

    def test_reused_replay_row_rejected(self):
        t, r = sample()
        with self.assertRaises(ValueError): bind_replay_to_transport(t, r, {
            "detect": {"source": "events", "source_index": 1},
            "correlate": {"source": "events", "source_index": 1}})

    def test_nonexistent_row_rejected(self):
        t, r = sample()
        with self.assertRaises(ValueError): bind_replay_to_transport(t, r, {"detect": {"source": "events", "source_index": 99}})

    def test_extra_binding_keys_rejected(self):
        t, r = sample()
        with self.assertRaises(ValueError): bind_replay_to_transport(t, r, {"detect": {"source": "events", "source_index": 1, "authenticated": True}})

    def test_unknown_cue_rejected(self):
        t, r = sample()
        with self.assertRaises(ValueError): bind_replay_to_transport(t, r, {"execute": {"source": "events", "source_index": 1}})

    def test_live_authority_rejected(self):
        t, r = sample()
        r["live_remediation_authorized"] = True
        with self.assertRaises(ValueError): bind_replay_to_transport(t, r, {})

    def test_unsafe_transport_rejected(self):
        t, r = sample()
        t["safety"]["remediation_authorized"] = True
        with self.assertRaises(ValueError): bind_replay_to_transport(t, r, {})

    def test_wrong_scene_order_rejected(self):
        t, r = sample()
        t["frames"][0], t["frames"][1] = t["frames"][1], t["frames"][0]
        with self.assertRaises(ValueError): bind_replay_to_transport(t, r, {})

    def test_export_end_to_end_offline_both_scenarios(self):
        for scenario in ("SAN_FABRIC_P1", "PAYMENTS_P2"):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                manifest = root / "manifest.json"
                manifest.write_text(json.dumps({"run_id": RUN_ID, "captures": {}}))
                run = {"run": {"run_id": RUN_ID, "mode": "DEMO", "status": "BLOCKED"},
                       "events": [{"timestamp": "2026-10-23T18:00:00Z"}], "stages": []}
                ledger = {"run_id": RUN_ID, "analyses": [], "critiques": [], "policy_decisions": []}
                evidence = {"run_id": RUN_ID, "items": []}
                result = export_legacy_portal_binding(manifest, root, scenario, run, ledger, evidence,
                    {"detect": {"source": "events", "source_index": 1}})
                self.assertEqual(result["scenario"], scenario)
                self.assertEqual(result["replay_status"], "BLOCKED")
                self.assertEqual(len(result["storyboard"]["frames"]), 9)
                self.assertTrue(all(x["capture_status"] == "missing" for x in result["storyboard"]["frames"]))
                self.assertFalse(result["safety"]["runtime_authenticated"])

    def test_extra_private_transport_metadata_not_exported(self):
        t, r = sample()
        t["private"] = "DO_NOT_EXPORT_PRIVATE"
        t["frames"][0]["secret"] = "DO_NOT_EXPORT_PRIVATE"
        doc = bind_replay_to_transport(t, r, {})
        self.assertNotIn("DO_NOT_EXPORT_PRIVATE", json.dumps(doc))

    def test_bad_replay_timestamp_rejected(self):
        t, r = sample()
        r["frames"][0]["timestamp"] = "secret-token-not-a-date"
        with self.assertRaises(ValueError): bind_replay_to_transport(t, r, {"detect": {"source": "events", "source_index": 1}})

    def test_bool_index_rejected(self):
        t, r = sample()
        with self.assertRaises(ValueError): bind_replay_to_transport(t, r, {"detect": {"source": "events", "source_index": True}})

    def test_duplicate_source_row_rejected(self):
        t, r = sample()
        r["frames"].append(dict(r["frames"][0]))
        with self.assertRaises(ValueError): bind_replay_to_transport(t, r, {})

    def test_out_of_order_declared_checkpoint_time_refused(self):
        t, r = sample()
        r["frames"][1]["timestamp"] = "2026-10-23T17:59:59Z"
        with self.assertRaisesRegex(ValueError, "nonmonotonic"):
            bind_replay_to_transport(t, r, {
                "detect": {"source": "events", "source_index": 1},
                "enrich": {"source": "stages", "source_index": 1}})

    def test_equal_declared_checkpoint_time_accepted_without_attestation(self):
        t, r = sample()
        r["frames"][1]["timestamp"] = "2026-10-23T18:00:00+00:00"
        doc = bind_replay_to_transport(t, r, {
            "detect": {"source": "events", "source_index": 1},
            "enrich": {"source": "stages", "source_index": 1}})
        self.assertFalse(doc["safety"]["runtime_authenticated"])
        self.assertEqual(doc["bindings"][2]["binding_status"], "operator_declared_unattested")


if __name__ == "__main__":
    unittest.main()
