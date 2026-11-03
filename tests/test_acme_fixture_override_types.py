"""ACME pinned graph/catalog type-integrity regressions (offline, SYNTHETIC)."""
import copy
import unittest

from tools import generate_acme_incidents as gen


class AcmeFixtureOverrideTypesTests(unittest.TestCase):
    def test_python_numeric_aliases_cannot_override_pinned_graph(self):
        graph = gen.load_graph()
        for section, field in (("nodes", "criticality"), ("edges", "redundancy")):
            with self.subTest(section=section):
                altered = copy.deepcopy(graph)
                key = next(iter(altered[section]))
                altered[section][key][field] = float(altered[section][key][field])
                self.assertEqual(altered, graph)  # Python's permissive numeric equality
                with self.assertRaisesRegex(ValueError, "unpinned graph override"):
                    gen.replay(graph=altered)

    def test_catalog_numeric_alias_cannot_change_dedupe_bucket(self):
        catalog, _ = gen.load_catalog()
        altered = copy.deepcopy(catalog)
        scenario = next(s for s in altered["scenarios"]
                        if s["key"] == "REDUNDANT_SAN_PATH_LOSS")
        scenario["frequency_seconds"] = float(scenario["frequency_seconds"])
        self.assertEqual(altered, catalog)
        with self.assertRaisesRegex(ValueError, "unpinned catalog override"):
            gen.replay(catalog=altered)

    def test_unchanged_replay_is_still_pinned_and_unattested(self):
        baseline = gen.replay()
        self.assertEqual(baseline, gen.replay(graph=gen.load_graph(), catalog=gen.load_catalog()[0]))
        self.assertEqual(baseline["event_count"], 7)
        self.assertEqual(baseline["correlation_status"], "OFFLINE_SYNTHETIC_ONLY")
        self.assertIsNone(baseline["incident_id"])
        self.assertIsNone(baseline["run_id"])
        self.assertEqual(baseline["evidence_ids"], [])
        self.assertTrue(all(c["status"] == "NOT_EXECUTED" for c in baseline["checkpoints"]))


if __name__ == "__main__":
    unittest.main()
