"""FS147: offline adversarial interleaving of two independent Twin traces.

No Debian, Docker, network, GLPI, PostgreSQL or live effects. The shared
schema/timestamps are intentional: isolation must rely on provenance, not time.
"""
import copy
import unittest

from test_fs147_twin_adapter_boundary_contract import LAB, SAN
from test_fs147_twin_cross_stage_receipt_contract import (
    STAGES, qualify_trace, synthetic_trace,
)


class InterleavedTwinRunIsolation(unittest.TestCase):
    def test_interleaved_replay_is_deterministic_and_nonmutating(self):
        lab, san = synthetic_trace(LAB), synthetic_trace(SAN)
        before = copy.deepcopy((lab, san))
        for index in range(len(STAGES)):
            # Alternate independently emitted receipts rather than accepting
            # a combined global stage stream as a single canonical Run.
            self.assertEqual(
                qualify_trace(copy.deepcopy(lab[:index + 1] + lab[index + 1:]), LAB, SAN)
                ["debian_e2e"], "UNVERIFIED"
            )
            self.assertEqual(
                qualify_trace(copy.deepcopy(san), SAN, LAB)["debian_e2e"], "UNVERIFIED"
            )
        self.assertEqual((lab, san), before)
        self.assertEqual(LAB["observed_at"], SAN["observed_at"])
        self.assertEqual(LAB["schema_version"], SAN["schema_version"])

    def test_foreign_receipt_substitution_at_every_boundary(self):
        for own, foreign in ((LAB, SAN), (SAN, LAB)):
            own_trace = synthetic_trace(own)
            foreign_trace = synthetic_trace(foreign)
            for index, stage in enumerate(STAGES):
                with self.subTest(own=own["graph"], stage=stage):
                    mixed = copy.deepcopy(own_trace)
                    mixed[index] = copy.deepcopy(foreign_trace[index])
                    with self.assertRaises(ValueError):
                        qualify_trace(mixed, own, foreign)

    def test_foreign_dependency_and_observation_do_not_bleed_on_replay(self):
        for own, foreign in ((LAB, SAN), (SAN, LAB)):
            baseline = synthetic_trace(own)
            for index, stage in enumerate(STAGES):
                with self.subTest(own=own["graph"], stage=stage):
                    poisoned = copy.deepcopy(baseline)
                    poisoned[index]["dependencies"][0]["to"] = foreign["evidence_ref"]
                    with self.assertRaises(ValueError):
                        qualify_trace(poisoned, own, foreign)
                    poisoned = copy.deepcopy(baseline)
                    poisoned[index]["observations"]["source_event_id"] = foreign["source_event_id"]
                    with self.assertRaises(ValueError):
                        qualify_trace(poisoned, own, foreign)
                    self.assertEqual(
                        qualify_trace(copy.deepcopy(baseline), own, foreign)["fixture"],
                        "QUALIFIED",
                    )


if __name__ == "__main__":
    unittest.main()
