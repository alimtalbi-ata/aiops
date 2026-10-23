"""Policy integration regression on isolated inputs, with autonomy state mocked."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from shared.simulation_policy_contract import policy_command_for_mode


class SimulationPolicyWiringTests(unittest.TestCase):
    def test_worker_uses_mapping_only_at_normal_policy_stage(self):
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / "app/shared/simulation_policy_contract.py").is_file())
        self.assertFalse((root / "shared/simulation_policy_contract.py").exists())
        worker = (root / "app/worker/main.py").read_text()
        self.assertIn("from shared.simulation_policy_contract import policy_command_for_mode", worker)
        self.assertIn("'command':policy_command_for_mode(mode)", worker)
        # Critic-denial policy must remain an EXECUTE request, therefore BLOCKED.
        self.assertIn("'command':'EXECUTE'", worker)

    def test_simulated_policy_passes_evidence_gate_without_disabling_live_stop(self):
        from app.policy.main import Decision, evaluate
        healthy = {"healthy": True, "mode": "NORMAL"}
        with patch("app.policy.main.autonomy_store.status", return_value=healthy), \
             patch.dict(os.environ, {"AIOPS_POLICY_EMERGENCY_STOP": "true"}):
            for mode in ("DEMO", "REPLAY", "STORY"):
                with self.subTest(mode=mode):
                    result = evaluate(Decision(
                        mode=mode, command=policy_command_for_mode(mode), severity="P1",
                        confidence=0.95, evidence_count=3, critic_validated=True,
                        redundancy_ok=True, evidence_fresh=True))
                    self.assertEqual((result["state"], result["decision"]), ("PASS", "SIMULATE"))
            live = evaluate(Decision(
                mode="LIVE", command=policy_command_for_mode("LIVE"), severity="P1",
                confidence=0.95, evidence_count=3, critic_validated=True,
                redundancy_ok=True, evidence_fresh=True))
            self.assertEqual((live["state"], live["decision"]), ("BLOCKED", "ESCALATE"))


if __name__ == "__main__":
    unittest.main()
