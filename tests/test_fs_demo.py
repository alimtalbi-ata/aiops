import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "fs_demo.py"

class SyntheticRemediation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = dict(os.environ, AIOPS_FS_DEMO_TEST_ROOT=self.tmp.name,
                        AIOPS_FS_DEMO_TEST_MODE="YES")

    def run_cmd(self, command, approval=False, run_id="RUN-TEST-01", ok=True):
        argv = [sys.executable, str(SCRIPT), command, "--run-id", run_id]
        if approval:
            argv += ["--approval", "SYNTHETIC_APPROVED"]
        p = subprocess.run(argv, env=self.env, capture_output=True, text=True)
        self.assertEqual(p.returncode == 0, ok, p.stderr)
        return json.loads(p.stdout) if ok else p.stderr

    def test_cleanup_rollback(self):
        self.run_cmd("init")
        self.run_cmd("propose")
        self.run_cmd("cleanup-logs", ok=False)
        s = self.run_cmd("cleanup-logs", approval=True)
        self.assertEqual((s["used_mib"], s["capacity_mib"]), (6,12))
        self.run_cmd("expand-fs", approval=True, ok=False)
        s = self.run_cmd("rollback", approval=True)
        self.assertEqual((s["used_mib"], s["capacity_mib"], s["incident"]), (11,12,"OPEN_SIMULATED"))

    def test_expand_rollback(self):
        self.run_cmd("init")
        self.run_cmd("propose")
        s = self.run_cmd("expand-fs", approval=True)
        self.assertEqual((s["used_mib"], s["capacity_mib"]), (11,16))
        self.run_cmd("finalize")
        self.run_cmd("cleanup-logs", approval=True, ok=False)
        self.run_cmd("rollback", approval=True, ok=False)

    def test_receipt_hash(self):
        self.run_cmd("init")
        path = Path(self.tmp.name) / "remediation" / "RUN-TEST-01"
        import hashlib
        receipt = json.loads((path / "receipt.json").read_text())
        self.assertEqual(receipt["state_sha256"], hashlib.sha256((path / "state.json").read_bytes()).hexdigest())

    def test_reject_bad_id(self):
        self.run_cmd("init", run_id="../escape", ok=False)

    def test_reject_reinit(self):
        self.run_cmd("init")
        self.run_cmd("init", ok=False)

    def test_proposal_required(self):
        self.run_cmd("init")
        self.run_cmd("cleanup-logs", approval=True, ok=False)

if __name__ == "__main__":
    unittest.main()
