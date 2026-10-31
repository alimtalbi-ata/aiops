"""Offline fail-closed tests for the selectively reused #206 staged inventory helper.

No install, upgrade, rollback, container, host or LIVE operation is performed.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "refresh_release_inventory.py"
SPEC = importlib.util.spec_from_file_location("staged_release_inventory", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class StagedInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "staged"
        (self.root / "manifests").mkdir(parents=True)
        (self.root / "app" / "core").mkdir(parents=True)
        (self.root / "README.md").write_bytes(b"new staged readme\n")
        (self.root / "app" / "core" / "main.py").write_bytes(b"print('fixture')\n")
        self.manifest = self.root / "manifests" / "MANIFEST.json"
        self.write_manifest([
            {"path": "README.md", "bytes": 0, "sha256": "0" * 64},
            {"path": "app/core/main.py", "bytes": 0, "sha256": "0" * 64},
        ])

    def write_manifest(self, entries):
        self.manifest.write_text(json.dumps({
            "release": "8.0.0", "name": "historical source",
            "files": entries,
        }), encoding="utf-8")

    def test_rebuilds_only_staged_digest_and_preserves_source_release(self):
        self.assertEqual(MODULE.refresh(self.root, "2.1.0-core-rc1.4"), 2)
        data = json.loads(self.manifest.read_text())
        self.assertEqual(data["release"], "2.1.0-core-rc1.4")
        self.assertEqual(data["source_manifest_release"], "8.0.0")
        self.assertEqual(data["inventory_kind"], "staged-release-file-digests")
        for entry in data["files"]:
            payload = (self.root / entry["path"]).read_bytes()
            self.assertEqual(entry["bytes"], len(payload))
            self.assertEqual(entry["sha256"], hashlib.sha256(payload).hexdigest())

    def test_repeat_keeps_original_historical_provenance(self):
        MODULE.refresh(self.root, "2.1.0-core-rc1.4")
        MODULE.refresh(self.root, "2.1.0-core-rc1.4")
        self.assertEqual(json.loads(self.manifest.read_text())["source_manifest_release"], "8.0.0")

    def test_invalid_release_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "invalid_release_version"):
            MODULE.refresh(self.root, "2.1.0\nqualification=PASS")

    def test_missing_listed_file_fails_closed(self):
        (self.root / "README.md").unlink()
        with self.assertRaisesRegex(ValueError, "embedded_manifest_file_missing"):
            MODULE.refresh(self.root, "2.1.0")

    def test_duplicate_entry_fails_closed(self):
        self.write_manifest([{"path": "README.md"}, {"path": "README.md"}])
        with self.assertRaisesRegex(ValueError, "embedded_manifest_path_invalid"):
            MODULE.refresh(self.root, "2.1.0")

    def test_path_traversal_fails_closed(self):
        self.write_manifest([{"path": "../outside"}])
        with self.assertRaisesRegex(ValueError, "embedded_manifest_path_invalid"):
            MODULE.refresh(self.root, "2.1.0")

    def test_self_referential_manifest_fails_closed(self):
        self.write_manifest([{"path": "manifests/MANIFEST.json"}])
        with self.assertRaisesRegex(ValueError, "embedded_manifest_path_invalid"):
            MODULE.refresh(self.root, "2.1.0")

    def test_symlink_file_fails_closed(self):
        (self.root / "README.md").unlink()
        (self.root / "README.md").symlink_to(self.root / "app" / "core" / "main.py")
        with self.assertRaisesRegex(ValueError, "embedded_manifest_file_missing"):
            MODULE.refresh(self.root, "2.1.0")

    def test_symlink_parent_fails_closed(self):
        (self.root / "app" / "core" / "main.py").unlink()
        (self.root / "app" / "core").rmdir()
        (self.root / "app" / "core").symlink_to(self.root / "manifests", target_is_directory=True)
        (self.root / "manifests" / "main.py").write_text("fixture")
        with self.assertRaisesRegex(ValueError, "embedded_manifest_file_missing"):
            MODULE.refresh(self.root, "2.1.0")

    def test_symlink_manifest_parent_fails_closed(self):
        (self.root / "manifests" / "MANIFEST.json").unlink()
        (self.root / "manifests").rmdir()
        other = self.root / "other"
        other.mkdir()
        (other / "MANIFEST.json").write_text('{"files":[{"path":"README.md"}]}')
        (self.root / "manifests").symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "embedded_manifest_missing_or_link"):
            MODULE.refresh(self.root, "2.1.0")

    def test_invalid_embedded_document_fails_closed(self):
        self.manifest.write_text('{"files":[]}')
        with self.assertRaisesRegex(ValueError, "embedded_manifest_invalid"):
            MODULE.refresh(self.root, "2.1.0")


if __name__ == "__main__":
    unittest.main()
