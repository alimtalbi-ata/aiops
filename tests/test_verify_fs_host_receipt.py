"""Offline fail-closed verifier tests; never attest a Debian host."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

p = Path(__file__).resolve().parents[1] / "deploy/verify-fs-host-receipt.py"
spec = importlib.util.spec_from_file_location("receipt_gate", p)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
RUN = "RUN-TEST-01"
SHA = "a" * 40

class ReceiptGateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        mock = patch.object(gate, "ROOT", self.root)
        mock.start()
        self.addCleanup(mock.stop)
        self.path = self.root / "runs" / RUN
        self.path.mkdir(parents=True)
        raw = json.dumps({"run_id": RUN}).encode()
        (self.path / "state.json").write_bytes(raw)
        self.receipt = dict(run_id=RUN, source_sha=SHA,
            state_sha256=hashlib.sha256(raw).hexdigest(),
            mode="SYNTHETIC_NO_EFFECT", host="SRV-DEB-05",
            collected_at="2026-11-05T02:00:00+00:00")
        self.save()

    def save(self):
        (self.path / "receipt.json").write_text(json.dumps(self.receipt))

    def test_valid_fixture_is_only_synthetic_receipt(self):
        self.assertEqual(gate.verify(self.path, RUN, SHA)["status"],
                         "VERIFIED_SYNTHETIC_RECEIPT_ONLY")

    def test_hash_tamper_refused(self):
        (self.path / "state.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "state hash mismatch"):
            gate.verify(self.path, RUN, SHA)

    def test_source_tamper_refused(self):
        self.receipt["source_sha"] = "b" * 40
        self.save()
        with self.assertRaisesRegex(ValueError, "source mismatch"):
            gate.verify(self.path, RUN, SHA)

    def test_host_tamper_refused(self):
        self.receipt["host"] = "UNKNOWN"
        self.save()
        with self.assertRaisesRegex(ValueError, "wrong host"):
            gate.verify(self.path, RUN, SHA)

    def test_symlink_refused(self):
        receipt = self.path / "receipt.json"
        other = self.root / "other.json"
        other.write_bytes(receipt.read_bytes())
        receipt.unlink()
        receipt.symlink_to(other)
        with self.assertRaisesRegex(ValueError, "symlink input"):
            gate.verify(self.path, RUN, SHA)

    def test_remediation_schema_not_mistaken_for_host_attestation(self):
        # fs_demo.py actually emits remediation/<run>, not runs/<run>.
        remediation = self.root / "remediation" / RUN
        remediation.mkdir(parents=True)
        (remediation / "state.json").write_bytes((self.path / "state.json").read_bytes())
        (remediation / "receipt.json").write_text(json.dumps({
            "run_id": RUN, "state_sha256": self.receipt["state_sha256"],
            "synthetic_only": True, "live_effects": False}))
        with self.assertRaises(ValueError):
            gate.verify(remediation, RUN, SHA)

if __name__ == "__main__":
    unittest.main()
