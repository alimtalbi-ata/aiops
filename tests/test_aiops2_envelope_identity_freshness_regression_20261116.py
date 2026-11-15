"""Fail-closed regression tests for synthetic signal-envelope trust boundaries.

These tests deliberately use DEMO fixtures; no network or LIVE source is contacted.
"""
import copy
import unittest

from scripts.aiops2_signal_envelope_guard_20261115 import normalize, deduplicate
from tests.test_aiops2_signal_envelope_guard_20261115 import BASE, NOW


class EnvelopeBoundaryRegression(unittest.TestCase):
    def test_forged_identity_key_cannot_hide_conflicting_event(self):
        first = normalize(BASE, now=NOW)
        second = normalize(dict(BASE, event_id="evt-2"), now=NOW)
        second["identity_key"] = first["identity_key"]
        with self.assertRaises(ValueError):
            deduplicate([first, second])

    def test_identity_key_must_match_normalized_identity(self):
        first = normalize(BASE, now=NOW)
        first["identity_key"] = ["other-tenant", "prometheus", "synthetic-1", "evt-1"]
        with self.assertRaises(ValueError):
            deduplicate([first])

    def test_missing_identity_key_rejected(self):
        first = normalize(BASE, now=NOW)
        del first["identity_key"]
        with self.assertRaises(ValueError):
            deduplicate([first])

    def test_freshness_parameter_rejects_invalid_values(self):
        for value in (None, True, False, -1, 0, float("nan"), float("inf"), "900", {}, []):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    normalize(copy.deepcopy(BASE), now=NOW, max_age_seconds=value)

    def test_freshness_threshold_is_deterministic(self):
        event = normalize(BASE, now=NOW, max_age_seconds=60)
        self.assertEqual(event["freshness"], "FRESH")
        event = normalize(BASE, now=NOW, max_age_seconds=59)
        self.assertEqual((event["freshness"], event["state"]), ("UNKNOWN", "UNKNOWN"))


if __name__ == "__main__":
    unittest.main()
