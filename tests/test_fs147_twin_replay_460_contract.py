"""Offline FS147/SAN replay isolation of PR #453's existing fixture validator.

No ingestion, database, network, Debian or real E2E evidence is exercised.
"""
import copy
import json
import unittest

from test_fs147_twin_adapter_boundary_contract import LAB, SAN, qualify_pair
from test_fs147_twin_nested_provenance_contract import reject_foreign_provenance


class TwinReplayIsolation(unittest.TestCase):
    def test_alternating_duplicate_deliveries_are_repeatable_and_immutable(self):
        originals = copy.deepcopy((LAB, SAN))
        expected = qualify_pair(LAB, SAN)
        for _ in range(3):
            for own, foreign in ((LAB, SAN), (SAN, LAB)):
                # JSON round-trip represents separate deliveries, not object aliases.
                event = json.loads(json.dumps(own))
                before = copy.deepcopy(event)
                self.assertIsNone(reject_foreign_provenance(event, foreign))
                self.assertEqual(event, before)
            self.assertEqual(qualify_pair(LAB, SAN), expected)
        self.assertEqual((LAB, SAN), originals)
        self.assertEqual(expected["live_fs147"], "UNKNOWN")

    def test_rejected_delivery_does_not_poison_next_scenario_or_replay(self):
        for own, foreign in ((LAB, SAN), (SAN, LAB)):
            with self.subTest(graph=own["graph"]):
                event = copy.deepcopy(own)
                event["metadata"] = {"evidence_ref": foreign["evidence_ref"]}
                before = copy.deepcopy(event)
                for _ in range(2):
                    with self.assertRaisesRegex(ValueError, "foreign SAN/FS provenance"):
                        reject_foreign_provenance(event, foreign)
                    self.assertEqual(event, before)
                    reject_foreign_provenance(copy.deepcopy(foreign), own)
                    reject_foreign_provenance(copy.deepcopy(own), foreign)

    def test_shared_observation_object_fails_closed_in_both_scenarios(self):
        for own, foreign in ((LAB, SAN), (SAN, LAB)):
            with self.subTest(graph=own["graph"]):
                event = copy.deepcopy(own)
                observation = {"source_event_id": own["source_event_id"]}
                event["observations"] = [observation, observation]
                with self.assertRaisesRegex(ValueError, "cyclic or aliased"):
                    reject_foreign_provenance(event, foreign)

    def test_equal_independent_observations_are_not_object_aliases(self):
        # This validator checks provenance, not ingestion idempotency. Identical
        # JSON observations are accepted; Core/Worker must deduplicate effects.
        for own, foreign in ((LAB, SAN), (SAN, LAB)):
            with self.subTest(graph=own["graph"]):
                event = copy.deepcopy(own)
                observation = {"source_event_id": own["source_event_id"]}
                event["observations"] = [copy.deepcopy(observation), copy.deepcopy(observation)]
                self.assertEqual(*event["observations"])
                self.assertIsNot(*event["observations"])
                reject_foreign_provenance(event, foreign)

    def test_duplicate_foreign_observations_still_fail_closed(self):
        for own, foreign in ((LAB, SAN), (SAN, LAB)):
            with self.subTest(graph=own["graph"]):
                event = copy.deepcopy(own)
                event["observations"] = [
                    {"source_event_id": foreign["source_event_id"]} for _ in range(2)
                ]
                with self.assertRaisesRegex(ValueError, "foreign SAN/FS provenance"):
                    reject_foreign_provenance(event, foreign)


if __name__ == "__main__":
    unittest.main()
