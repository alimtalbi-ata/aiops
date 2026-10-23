import copy
import json
import unittest
from demo.star_legacy_replay_adapter import build_replay

RUN = "RUN-STAR-TEST-001"


def fixture(status="RESOLVED"):
    return (
        {"run": {"run_id": RUN, "mode": "DEMO", "status": status},
         "events": [{"event_id": "PRIVATE_EVENT", "severity": "P1", "evidence_ids": ["EVID-001"],
                     "timestamp": "2026-10-23T18:00:00Z", "secret": "NEVER_LEAK"}],
         "stages": [{"name": "ingress", "timestamp": "2026-10-23T18:00:01Z"}]},
        {"run_id": RUN,
         "analyses": [{"confidence": 0.9, "timestamp": "2026-10-23T18:00:02Z"}],
         "critiques": [{"validated": True, "timestamp": "2026-10-23T18:00:03Z"}],
         "policy_decisions": [{"status": "SIMULATE", "timestamp": "2026-10-23T18:00:04Z"}]},
        {"run_id": RUN, "items": [{"evidence_id": "EVID-001", "customer": "NEVER_LEAK"}]},
    )


class HistoricalReplayAdapterTests(unittest.TestCase):
    def test_resolved_and_blocked_demo(self):
        for status in ("RESOLVED", "BLOCKED"):
            with self.subTest(status=status):
                doc = build_replay(*fixture(status))
                self.assertEqual(doc["status"], status)
                self.assertEqual(len(doc["frames"]), 5)
                self.assertTrue(doc["chronology_proven_from_declared_timestamps"])
                self.assertFalse(doc["live_remediation_authorized"])
                self.assertFalse(doc["runtime_authenticated"])

    def test_determinism_and_private_data_not_exported(self):
        data = fixture()
        a = build_replay(*data)
        self.assertEqual(a, build_replay(*copy.deepcopy(data)))
        self.assertNotIn("NEVER_LEAK", json.dumps(a))
        self.assertNotIn("PRIVATE_EVENT", json.dumps(a))
        self.assertNotIn("EVID-001", json.dumps(a))

    def test_mismatched_identity_rejected(self):
        data = list(fixture())
        data[1]["run_id"] = "RUN-OTHER-002"
        with self.assertRaises(ValueError):
            build_replay(*data)

    def test_live_rejected(self):
        data = list(fixture())
        data[0]["run"]["mode"] = "LIVE"
        with self.assertRaises(ValueError):
            build_replay(*data)

    def test_unknown_evidence_rejected(self):
        data = list(fixture())
        data[0]["events"][0]["evidence_ids"] = ["EVID-OTHER"]
        with self.assertRaises(ValueError):
            build_replay(*data)

    def test_duplicate_evidence_rejected(self):
        data = list(fixture())
        data[2]["items"].append({"evidence_id": "EVID-001"})
        with self.assertRaises(ValueError):
            build_replay(*data)

    def test_untrusted_or_naive_timestamp_never_claims_chronology(self):
        data = list(fixture())
        data[0]["events"][0]["timestamp"] = "2026-10-23T18:00:00"
        doc = build_replay(*data)
        self.assertFalse(doc["chronology_proven_from_declared_timestamps"])
        self.assertIsNone(doc["frames"][0]["timestamp"])

    def test_non_finite_confidence_rejected_from_fingerprint(self):
        data = list(fixture())
        data[1]["analyses"][0]["confidence"] = float("nan")
        with self.assertRaises(ValueError):
            build_replay(*data)

    def test_original_v2134_short_evidence_ids_supported(self):
        data = list(fixture("BLOCKED"))
        data[0]["events"][0]["evidence_ids"] = ["E1"]
        data[2]["items"][0]["evidence_id"] = "E1"
        doc = build_replay(*data)
        self.assertEqual(doc["frames"][0]["evidence_ref_count"], 1)

    def test_no_frames_never_claims_chronology(self):
        data = list(fixture())
        for key in ("events", "stages"):
            data[0][key] = []
        for key in ("analyses", "critiques", "policy_decisions"):
            data[1][key] = []
        doc = build_replay(*data)
        self.assertEqual(doc["frames"], [])
        self.assertFalse(doc["chronology_proven_from_declared_timestamps"])


if __name__ == "__main__":
    unittest.main()
