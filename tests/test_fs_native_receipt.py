"""Offline tests for the native #423 receipt verifier; never touch Debian."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "deploy" / "verify-fs-native-remediation.py"
spec = importlib.util.spec_from_file_location("native_receipt", MODULE)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)

class NativeReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = "DEMO-TEST-01"
        self.path = self.root / "remediation" / self.run
        self.path.mkdir(parents=True)
        self.state = dict(run_id=self.run, incident="OPEN_SIMULATED", proposed=None,
                          action=None, phase="OPEN", used_mib=11, capacity_mib=12)
        self.write()

    def write(self):
        raw = (json.dumps(self.state, sort_keys=True) + "\n").encode()
        (self.path / "state.json").write_bytes(raw)
        self.receipt = {**self.state, "command": "init", "state_sha256": hashlib.sha256(raw).hexdigest(),
                        "synthetic_only": True, "live_effects": False}
        (self.path / "receipt.json").write_text(json.dumps(self.receipt))

    def test_native_valid_no_host_claim(self):
        result = native.verify(self.run, self.root)
        self.assertEqual(result["host_provenance"], "NOT_ATTESTED")

    def test_tampered_state(self):
        (self.path / "state.json").write_text('{"run_id":"DEMO-TEST-01"}')
        with self.assertRaisesRegex(ValueError, "digest"):
            native.verify(self.run, self.root)

    def test_unsafe_live_flag(self):
        self.receipt["live_effects"] = True
        (self.path / "receipt.json").write_text(json.dumps(self.receipt))
        with self.assertRaisesRegex(ValueError, "unsafe"):
            native.verify(self.run, self.root)

    def test_mismatched_incident(self):
        self.receipt["incident"] = "MITIGATED_SIMULATED"
        (self.path / "receipt.json").write_text(json.dumps(self.receipt))
        with self.assertRaisesRegex(ValueError, "mismatch"):
            native.verify(self.run, self.root)

    def test_symlink_input(self):
        (self.path / "receipt.json").unlink()
        (self.path / "receipt.json").symlink_to(self.path / "state.json")
        with self.assertRaisesRegex(ValueError, "symlink"):
            native.verify(self.run, self.root)

    def test_invalid_run(self):
        with self.assertRaisesRegex(ValueError, "run-id"):
            native.verify("../escape", self.root)

if __name__ == "__main__":
    unittest.main()
