"""Offline simulation command contract; no Policy API or LIVE executor calls."""
import unittest

from shared.simulation_policy_contract import policy_command_for_mode


class SimulationPolicyContractTests(unittest.TestCase):
    def test_simulation_modes_never_request_an_effect(self):
        for mode in ("DEMO", "REPLAY", "STORY"):
            with self.subTest(mode=mode):
                self.assertEqual(policy_command_for_mode(mode), "OBSERVE")

    def test_live_keeps_effect_command_for_strict_policy_denial(self):
        self.assertEqual(policy_command_for_mode("LIVE"), "EXECUTE")

    def test_unknown_or_malformed_modes_fail_closed(self):
        for mode in ("", "demo", "SIMULATE", None, {}, 0):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                policy_command_for_mode(mode)


if __name__ == "__main__":
    unittest.main()
