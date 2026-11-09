"""Read-only round-trip receipt contract tests."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ops" / "coordination"))
from verify_codex_roundtrip import verify

def receipt():
    return {"schema_version": "aiops.codex-roundtrip.v1", "correlation_id": "FS1250-001",
            "work_id": "457/bridge/read-only", "executor": "codex.cli.debian",
            "session_id": "codex-session-001", "started_at": "2026-11-09T10:00:00Z",
            "finished_at": "2026-11-09T10:01:00Z", "source_sha": "a"*40,
            "result_sha": "b"*40, "task_url": "https://github.com/alimtalbi-ata/aiops/issues/464",
            "result_url": "https://github.com/alimtalbi-ata/aiops/issues/464",
            "exit_code": 0, "evidence_kind": "OBSERVED"}

class RoundtripTests(unittest.TestCase):
    def test_structural_claim_not_external_verification(self):
        self.assertEqual(verify(receipt())["status"], "STRUCTURALLY_VALID_OBSERVED_CLAIM")
    def test_no_session(self):
        r=receipt();r["session_id"]="";self.assertRaises(ValueError,verify,r)
    def test_no_synthetic_promotion(self):
        r=receipt();r["evidence_kind"]="SYNTHETIC";self.assertRaises(ValueError,verify,r)
    def test_nonzero_exit(self):
        r=receipt();r["exit_code"]=1;self.assertRaises(ValueError,verify,r)
    def test_wrong_work(self):
        self.assertRaises(ValueError,verify,receipt(),"another-work")
    def test_external_url(self):
        r=receipt();r["result_url"]="https://example.com/";self.assertRaises(ValueError,verify,r)

if __name__ == "__main__":
    unittest.main()
