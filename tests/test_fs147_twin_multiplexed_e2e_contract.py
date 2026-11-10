"""FS147: compose lossless stream partition with per-stage provenance qualification.

Synthetic contract only. No Docker, Debian, database or external calls.
"""
import copy
import unittest

from test_fs147_twin_adapter_boundary_contract import LAB, SAN
from test_fs147_twin_cross_stage_receipt_contract import synthetic_trace, qualify_trace, STAGES
from test_fs147_twin_stream_partition_contract import partition_receipts, IDENTITY


def key(own):
    return tuple(own[field] for field in IDENTITY)


def qualify_multiplexed(stream):
    """Both full traces must pass; a partition alone is never qualification."""
    groups = partition_receipts(stream, expected=(LAB, SAN))
    return {
        "filesystem": qualify_trace(groups[key(LAB)], LAB, SAN),
        "san": qualify_trace(groups[key(SAN)], SAN, LAB),
    }


class TwinMultiplexedE2EContract(unittest.TestCase):
    def setUp(self):
        fs = synthetic_trace(LAB)
        san = synthetic_trace(SAN)
        self.stream = [item for pair in zip(fs, san) for item in pair]

    def test_full_bidirectional_chain_and_replay(self):
        before = copy.deepcopy(self.stream)
        result = qualify_multiplexed(self.stream)
        self.assertEqual(result["filesystem"]["fixture"], "QUALIFIED")
        self.assertEqual(result["san"]["fixture"], "QUALIFIED")
        self.assertEqual(result["filesystem"]["debian_e2e"], "UNVERIFIED")
        self.assertEqual(result["san"]["debian_e2e"], "UNVERIFIED")
        self.assertEqual(qualify_multiplexed(self.stream), result)
        self.assertEqual(self.stream, before)

    def test_partition_acceptance_cannot_launder_foreign_nested_provenance(self):
        for own, foreign in ((LAB, SAN), (SAN, LAB)):
            for stage_index, stage in enumerate(STAGES):
                for field in ("observations", "dependencies"):
                    with self.subTest(graph=own["graph"], stage=stage, field=field):
                        poisoned = copy.deepcopy(self.stream)
                        receipt = next(r for r in poisoned if r["run_id"] == own["run_id"] and r["stage"] == stage)
                        if field == "observations":
                            receipt["observations"]["source_event_id"] = foreign["source_event_id"]
                        else:
                            receipt["dependencies"][0]["to"] = foreign["evidence_ref"]
                        # Demultiplexing checks identity and order only; it must
                        # never be mistaken for provenance qualification.
                        partition_receipts(poisoned, expected=(LAB, SAN))
                        with self.assertRaises(ValueError):
                            qualify_multiplexed(poisoned)
                        self.assertEqual(qualify_multiplexed(self.stream)["filesystem"]["fixture"], "QUALIFIED")

    def test_no_partial_success_when_one_run_is_missing_or_foreign(self):
        missing = [r for r in self.stream if r["run_id"] != SAN["run_id"]]
        with self.assertRaises(ValueError):
            qualify_multiplexed(missing)
        foreign = copy.deepcopy(self.stream)
        foreign[0]["namespace"] = SAN["namespace"]
        with self.assertRaises(ValueError):
            qualify_multiplexed(foreign)


if __name__ == "__main__":
    unittest.main()
