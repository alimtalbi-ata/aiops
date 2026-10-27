"""Tests for the read-only historical replay dependency audit."""
import hashlib
import json
import tempfile
import zipfile
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


    def test_archive_is_inspected_without_extraction_and_exact_hashes_are_required(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "historical.zip"
            fixture_bytes = {
                "tools/build_real_replay.py": b"original builder fixture",
                "tests/test_replay.py": b"original test fixture",
            }
            expected = {
                relative: {"sha256": hashlib.sha256(data).hexdigest(), "role": "fixture"}
                for relative, data in fixture_bytes.items()
            }
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for relative, data in fixture_bytes.items():
                    zf.writestr(relative, data)
            with patch.dict("recovery.legacy_v2134.tools.audit_hybrid_dependencies.EXPECTED", expected, clear=True):
                result = audit(root / "empty-tree", archive)
        self.assertEqual(result["archive_audit"]["status"], "CRC_PASS")
        self.assertTrue(result["archive_recovery_complete"])
        self.assertFalse(result["source_execution_performed"])
        self.assertFalse((root / "empty-tree").exists())

    def test_archive_with_duplicate_expected_member_is_not_accepted(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "duplicate.zip"
            expected = {
                "tools/build_real_replay.py": {"sha256": hashlib.sha256(b"source").hexdigest(), "role": "fixture"},
            }
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("tools/build_real_replay.py", b"source")
                zf.writestr("tools/build_real_replay.py", b"source")
            with patch.dict("recovery.legacy_v2134.tools.audit_hybrid_dependencies.EXPECTED", expected, clear=True):
                result = audit(root / "empty-tree", archive)
        self.assertEqual(result["archive_audit"]["status"], "CRC_OR_DUPLICATE_FAILURE")
        self.assertFalse(result["archive_recovery_complete"])
        self.assertEqual(result["archive_audit"]["members"][0]["status"], "DUPLICATE_MEMBER")


    def test_archive_symlink_member_is_rejected(self):
        from unittest.mock import patch
        import stat
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "symlink.zip"
            expected = {
                "tools/build_real_replay.py": {
                    "sha256": hashlib.sha256(b"target").hexdigest(),
                    "role": "fixture",
                },
            }
            info = zipfile.ZipInfo("tools/build_real_replay.py")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr(info, b"target")
            with patch.dict("recovery.legacy_v2134.tools.audit_hybrid_dependencies.EXPECTED", expected, clear=True):
                result = audit(root / "empty-tree", archive)
        self.assertEqual(result["archive_audit"]["status"], "CRC_PASS")
        self.assertEqual(result["archive_audit"]["members"][0]["status"], "REJECTED_SYMLINK")
        self.assertFalse(result["archive_recovery_complete"])

    def test_malformed_archive_is_reported_without_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "broken.zip"
            archive.write_bytes(b"this is not a zip archive")
            result = audit(root / "empty-tree", archive)
        self.assertEqual(result["archive_audit"]["status"], "INVALID_ARCHIVE")
        self.assertFalse(result["archive_recovery_complete"])
        self.assertFalse(result["source_execution_performed"])

if __name__ == "__main__":
    unittest.main()
