"""Unit tests for the read-only evidence matrix projection."""
import datetime
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from shared.evidence_matrix import build_evidence_matrix


NOW = datetime.datetime(2026, 10, 27, 12, 0, tzinfo=datetime.timezone.utc)


def item(eid="E1", **overrides):
    value = {
        "evidence_id": eid,
        "source": "synthetic-san-monitor",
        "external_id": "RUN-1:path-1",
        "observed_at": "2026-10-27T11:59:00Z",
        "claim": "SAN path degraded",
        "confidence": 0.9,
        "provenance": {"synthetic": True, "run_id": "RUN-1"},
        "payload": {"active_paths": 1, "total_paths": 4},
    }
    value.update(overrides)
    return value


class EvidenceMatrixTests(unittest.TestCase):
    def test_fresh_evidence_is_reviewable_but_never_authorizes_action(self):
        result = build_evidence_matrix(
            [item()], [{"hypothesis_id": "H-SAN", "supporting_evidence_ids": ["E1"]}],
            now=NOW, max_age_seconds=900,
        )
        self.assertEqual(result["schema"], "aiops.evidence-matrix-read-model.v1")
        self.assertEqual(result["status"], "READY_FOR_REVIEW")
        self.assertFalse(result["action_authorized"])
        self.assertEqual(result["decision_authority"], "NONE_READ_MODEL_ONLY")
        self.assertEqual(result["items"][0]["freshness"], "FRESH")
        self.assertEqual(result["items"][0]["provenance"], "SYNTHETIC")
        self.assertEqual(result["items"][0]["hypotheses"], [
            {"hypothesis": "H-SAN", "relation": "SUPPORTS"}
        ])

    def test_missing_timestamp_remains_unknown(self):
        result = build_evidence_matrix([item(observed_at=None)], now=NOW)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["items"][0]["freshness"], "UNKNOWN")
        self.assertEqual(result["items"][0]["freshness_reason"], "observed_at_missing_or_timezone_ambiguous")

    def test_stale_evidence_degrades_review_status(self):
        result = build_evidence_matrix(
            [item(observed_at="2026-10-26T00:00:00Z")], now=NOW, max_age_seconds=900
        )
        self.assertEqual(result["status"], "DEGRADED_REVIEW")
        self.assertEqual(result["items"][0]["freshness"], "STALE")

    def test_duplicate_evidence_id_blocks_review(self):
        result = build_evidence_matrix([item(), item()], now=NOW)
        self.assertEqual(result["status"], "BLOCKED_FOR_REVIEW")
        self.assertIn("duplicate_evidence_id:E1", result["contract_errors"])

    def test_non_object_input_is_retained_as_invalid_row(self):
        result = build_evidence_matrix([None], now=NOW)
        self.assertEqual(result["status"], "BLOCKED_FOR_REVIEW")
        self.assertEqual(result["items"][0]["integrity"], "INVALID")
        self.assertEqual(result["items"][0]["freshness"], "UNKNOWN")

    def test_contradictory_snapshots_are_exposed_without_selecting_truth(self):
        second = item(
            "E2", external_id="RUN-1:path-2",
            payload={"active_paths": 4, "total_paths": 4},
        )
        result = build_evidence_matrix([item(), second], now=NOW)
        self.assertEqual(len(result["contradictions"]), 1)
        self.assertEqual(result["contradictions"][0]["code"], "DIVERGENT_PATH_SNAPSHOTS")
        self.assertEqual(result["status"], "DEGRADED_REVIEW")

    def test_claimed_non_synthetic_is_not_called_attested(self):
        result = build_evidence_matrix(
            [item(provenance={"synthetic": False})], now=NOW
        )
        self.assertEqual(result["items"][0]["provenance"], "NON_SYNTHETIC_CLAIMED")
        self.assertNotEqual(result["items"][0]["integrity"], "HASH_VERIFIED")

    def test_empty_collection_is_unknown(self):
        result = build_evidence_matrix([], now=NOW)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertFalse(result["action_authorized"])
        self.assertEqual(result["evidence_count"], 0)

    def test_non_list_evidence_is_blocked_not_misreported_as_empty(self):
        result = build_evidence_matrix({"evidence_id": "E1"}, now=NOW)
        self.assertEqual(result["status"], "BLOCKED_FOR_REVIEW")
        self.assertIn("evidence_collection_not_a_list", result["input_errors"])
        self.assertEqual(result["evidence_count"], 0)
        self.assertFalse(result["action_authorized"])

    def test_non_list_hypotheses_are_reported_without_raising(self):
        result = build_evidence_matrix([item()], hypotheses={"hypothesis_id": "H1"}, now=NOW)
        self.assertEqual(result["status"], "BLOCKED_FOR_REVIEW")
        self.assertIn("hypotheses_collection_not_a_list", result["input_errors"])
        self.assertEqual(result["hypothesis_count"], 0)

    def test_non_object_hypothesis_blocks_review_and_is_counted(self):
        result = build_evidence_matrix([item()], hypotheses=[None], now=NOW)
        self.assertEqual(result["status"], "BLOCKED_FOR_REVIEW")
        self.assertIn("hypothesis_not_an_object:0", result["input_errors"])
        self.assertEqual(result["hypothesis_count"], 1)

    def test_duplicate_id_prefix_does_not_invalidate_unrelated_evidence(self):
        result = build_evidence_matrix(
            [item("E1"), item("E10"), item("E10")], now=NOW
        )
        self.assertEqual(result["status"], "BLOCKED_FOR_REVIEW")
        self.assertEqual(result["items"][0]["integrity"], "UNVERIFIED")
        self.assertEqual(result["items"][1]["integrity"], "INVALID")
        self.assertEqual(result["items"][2]["integrity"], "INVALID")


if __name__ == "__main__":
    unittest.main()
