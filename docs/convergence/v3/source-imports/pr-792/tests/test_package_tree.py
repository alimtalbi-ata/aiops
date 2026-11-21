import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("aiops_package_tree", ROOT / "deploy" / "package_tree.py")
PKG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PKG)


def build_source(root):
    for relative in PKG.REQUIRED_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture " + relative + "\n", encoding="utf-8")
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / ".env.example").write_text("POSTGRES_PASSWORD=\n")
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "architecture.md").write_text("# fixture architecture\n")
    (root / "reports").mkdir(exist_ok=True)
    (root / "reports" / "live-evidence.json").write_text('{"secret":"no"}')
    (root / ".env").write_text("POSTGRES_PASSWORD=never-copy-me")
    (root / "backups").mkdir(exist_ok=True)
    (root / "backups" / "private.dump").write_bytes(b"PRIVATE")
    (root / "app" / "worker" / "__pycache__").mkdir(exist_ok=True)
    (root / "app" / "worker" / "__pycache__" / "x.pyc").write_bytes(b"PYC")
    (root / "docs" / "hidden.pem").write_text("PRIVATE KEY")


class OfflinePackagingTests(unittest.TestCase):
    def test_whitelist_copies_installable_sources_not_private_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            root = folder / "src"
            output = folder / "copy"
            root.mkdir()
            build_source(root)
            count = PKG.prepare_copy(root, output)
            self.assertGreaterEqual(count, len(PKG.REQUIRED_FILES))
            self.assertTrue((output / "app" / "worker" / "workflow.py").exists())
            self.assertTrue((output / "config" / ".env.example").exists())
            self.assertTrue((output / "docs" / "architecture.md").exists())
            self.assertFalse((output / ".env").exists())
            self.assertFalse((output / "reports").exists())
            self.assertFalse((output / "backups").exists())
            self.assertFalse((output / "docs" / "hidden.pem").exists())
            self.assertFalse((output / "app" / "worker" / "__pycache__").exists())

    def test_symlinked_secret_is_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            root = folder / "src"
            output = folder / "copy"
            root.mkdir()
            build_source(root)
            (root / "docs" / "external-secret.txt").symlink_to(root / ".env")
            PKG.prepare_copy(root, output)
            self.assertFalse((output / "docs" / "external-secret.txt").exists())

    def test_source_destination_overlap_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "src"
            root.mkdir()
            build_source(root)
            with self.assertRaises(PKG.PackagingError):
                PKG.prepare_copy(root, root / "dist")
            with self.assertRaises(PKG.PackagingError):
                PKG.prepare_copy(root, root)
            with self.assertRaises(PKG.PackagingError):
                PKG.prepare_copy(root, root.parent)

    def test_missing_critical_source_is_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "src"
            root.mkdir()
            build_source(root)
            (root / "deploy" / "migrate.sh").unlink()
            with self.assertRaisesRegex(PKG.PackagingError, "required_source_missing"):
                PKG.prepare_copy(root, pathlib.Path(tmp) / "dest")


if __name__ == "__main__":
    unittest.main()
