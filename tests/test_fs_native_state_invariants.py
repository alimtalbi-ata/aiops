"""Offline negative tests: coherent hashes must not conceal impossible synthetic states."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "verify-fs-native-remediation.py"
spec = importlib.util.spec_from_file_location("native_receipt_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class NativeStateInvariants(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = "SYNTHETIC-001"
        self.path = self.root / "remediation" / self.run
        self.path.mkdir(parents=True)
        self.state = dict(run_id=self.run, used_mib=11, capacity_mib=12, logs_mib=5,
                          incident="OPEN_SIMULATED", phase="OPEN", proposed=None,
                          action=None, rollback_closed=True)

    def write(self):
        raw = (json.dumps(self.state, sort_keys=True) + "\n").encode()
        (self.path / "state.json").write_bytes(raw)
        receipt = {k: self.state[k] for k in
                   ("run_id", "incident", "proposed", "action", "phase", "used_mib", "capacity_mib")}
        receipt.update(state_sha256=hashlib.sha256(raw).hexdigest(),
                       synthetic_only=True, live_effects=False)
        (self.path / "receipt.json").write_text(json.dumps(receipt))

    def test_open_valid(self):
        self.write()
        self.assertEqual(gate.verify(self.run, self.root)["status"], "NATIVE_SYNTHETIC_RECEIPT_VALID_ONLY")

    def test_open_rollback_not_closed_rejected(self):
        self.state["rollback_closed"] = False
        self.write()
        with self.assertRaisesRegex(ValueError, "inconsistent open state"):
            gate.verify(self.run, self.root)

    def test_open_usage_forgery_rejected_with_matching_digest(self):
        self.state["used_mib"] = 6
        self.write()
        with self.assertRaisesRegex(ValueError, "inconsistent open state"):
            gate.verify(self.run, self.root)

    def test_applied_valid(self):
        self.state.update(phase="ACTION_APPLIED", incident="MITIGATED_SIMULATED",
                          proposed="cleanup-logs", action="cleanup-logs",
                          rollback_closed=False, used_mib=6, logs_mib=0)
        self.write()
        self.assertEqual(gate.verify(self.run, self.root)["status"], "NATIVE_SYNTHETIC_RECEIPT_VALID_ONLY")

    def test_applied_rollback_closed_rejected(self):
        self.state.update(phase="ACTION_APPLIED", incident="MITIGATED_SIMULATED",
                          proposed="cleanup-logs", action="cleanup-logs",
                          rollback_closed=True, used_mib=6, logs_mib=0)
        self.write()
        with self.assertRaisesRegex(ValueError, "inconsistent mitigated state"):
            gate.verify(self.run, self.root)

    def test_expand_capacity_forgery_rejected(self):
        self.state.update(phase="FINALIZED_SIMULATED", incident="MITIGATED_SIMULATED",
                          proposed="cleanup-logs", action="expand-fs",
                          rollback_closed=False, capacity_mib=32)
        self.write()
        with self.assertRaisesRegex(ValueError, "inconsistent synthetic action"):
            gate.verify(self.run, self.root)

if __name__ == "__main__":
    unittest.main()
