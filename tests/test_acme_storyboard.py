"""Contract tests for the offline ACME explanatory storyboard."""
import unittest
from copy import deepcopy

from app.shared.acme_storyboard import build_acme_storyboard


class AcmeStoryboardTests(unittest.TestCase):
    def test_six_explanatory_steps(self):
        result = build_acme_storyboard()
        self.assertEqual(len(result["steps"]), 6)
        self.assertEqual(result["steps"][0]["step_id"], "san")
        self.assertEqual(result["steps"][-1]["step_id"], "remediation")
        self.assertEqual(result["mode"], "OFFLINE_PRESENTATION")

    def test_missing_sources_are_unknown(self):
        self.assertTrue(all(s["source_status"] == "UNKNOWN"
                            for s in build_acme_storyboard()["steps"]))

    def test_caller_reference_not_attested(self):
        result = build_acme_storyboard(observed={"san": {
            "source": "core", "reference": "RUN-ACME-1",
            "runtime_verified": True, "effect_applied": True}})
        step = result["steps"][0]
        self.assertEqual(step["source_status"], "CALLER_SUPPLIED_UNVERIFIED")
        self.assertFalse(step["runtime_verified"])
        self.assertFalse(step["effect_applied"])
        self.assertFalse(result["runtime_attested"])

    def test_no_freeform_payload_leak(self):
        result = build_acme_storyboard(observed={"san": {
            "source": "core", "reference": "RUN-ACME-1",
            "secret": "do-not-publish", "payload": {"token": "secret"}}})
        self.assertNotIn("do-not-publish", str(result))
        self.assertNotIn("token", str(result))

    def test_bad_step_refused(self):
        with self.assertRaises(ValueError):
            build_acme_storyboard(observed={"invented": {}})

    def test_bad_input_refused(self):
        with self.assertRaises(ValueError):
            build_acme_storyboard(observed=[])

    def test_bad_observation_refused(self):
        with self.assertRaises(ValueError):
            build_acme_storyboard(observed={"san": "verified"})

    def test_source_without_reference_stays_unknown(self):
        result = build_acme_storyboard(observed={"san": {"source": "core"}})
        self.assertEqual(result["steps"][0]["source_status"], "UNKNOWN")

    def test_no_mutation(self):
        data = {"san": {"source": "core", "reference": "RUN-ACME-1"}}
        original = deepcopy(data)
        build_acme_storyboard(observed=data)
        self.assertEqual(data, original)


if __name__ == "__main__":
    unittest.main()
