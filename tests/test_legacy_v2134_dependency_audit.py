"""Tests for the read-only historical replay dependency audit."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from recovery.legacy_v2134.tools.audit_hybrid_dependencies import EXPECTED, audit


class LegacyHybridDependencyAuditTests(unittest.TestCase):
    def test_missing_members_are_reported_without_claiming_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = audit(Path(tmp))
        self.assertFalse(result["recovery_complete"])
        self.assertEqual(result["decision"], "RECOVERY_INCOMPLETE")
        self.assertFalse(result["source_execution_performed"])
        self.assertFalse(result["runtime_qualification"])
        self.assertEqual([m["status"] for m in result["members"]], ["MISSING", "MISSING"])
        self.assertTrue(all(m["observed_sha256"] is None for m in result["members"]))

    def test_exact_historical_hashes_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative, metadata in EXPECTED.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                # The audit must not accept merely present or syntactically valid code.
                path.write_bytes(b"not the historical bytes")
            result = audit(root)
        self.assertFalse(result["recovery_complete"])
        self.assertEqual([m["status"] for m in result["members"]], ["HASH_MISMATCH", "HASH_MISMATCH"])

    def test_matching_hashes_are_only_a_review_gate_not_runtime_qualification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative, metadata in EXPECTED.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                # Synthetic fixture whose digest is monkeypatched only for this isolated test.
                path.write_bytes(b"synthetic")
            from unittest.mock import patch
            with patch("recovery.legacy_v2134.tools.audit_hybrid_dependencies.hashlib.sha256") as sha:
                sha.return_value.hexdigest.side_effect = [m["sha256"] for m in EXPECTED.values()]
                result = audit(root)
        self.assertTrue(result["recovery_complete"])
        self.assertEqual(result["decision"], "READY_FOR_SEPARATE_REVIEW")
        self.assertFalse(result["runtime_qualification"])

    def test_symlinked_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "elsewhere"
            target.write_bytes(b"historical-looking bytes")
            path = root / "tools/build_real_replay.py"
            path.parent.mkdir(parents=True)
            path.symlink_to(target)
            result = audit(root)
        self.assertEqual(result["members"][0]["status"], "REJECTED_SYMLINK")
        self.assertFalse(result["recovery_complete"])


if __name__ == "__main__":
    unittest.main()
