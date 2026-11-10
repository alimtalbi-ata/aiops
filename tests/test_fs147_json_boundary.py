"""Reject non-JSON adapter metadata before Analyst/Critic/Policy can trust it."""
import math
import unittest
from worker.fs147_readonly_pipeline import _claims_side_effect


class FS147JSONBoundaryTests(unittest.TestCase):
    def test_opaque_values_and_non_string_keys_fail_closed(self):
        payloads = (
            {"metadata": {1: "approval_token"}},
            {"metadata": {None: "NO_EFFECT"}},
            {"metadata": {"values": {1, 2}}},
            {"metadata": {"raw": b"approval_token"}},
            {"metadata": {"object": object()}},
            {"metadata": {"sample": float("nan")}},
            {"metadata": {"sample": float("inf")}},
            {"metadata": {"sample": -float("inf")}},
            {"metadata": {"tuple": ({"effect": "LIVE"},)}},
        )
        for payload in payloads:
            with self.subTest(payload=repr(payload)):
                self.assertTrue(_claims_side_effect(payload))

    def test_json_metadata_remains_compatible(self):
        payload = {"metadata": {"sample": 0.5, "count": 2, "enabled": False,
                                "nothing": None, "labels": ["fs-lab", "read-only"],
                                "nested": {"dry_run": True,
                                           "execution_mode": "SIMULATE",
                                           "effect": "NO_EFFECT"}}}
        self.assertFalse(_claims_side_effect(payload))

    def test_cyclic_and_deep_payloads_remain_denied(self):
        cycle = []
        cycle.append(cycle)
        self.assertTrue(_claims_side_effect({"metadata": cycle}))
        deep = {}
        for _ in range(18):
            deep = {"metadata": deep}
        self.assertTrue(_claims_side_effect(deep))


if __name__ == "__main__":
    unittest.main()
