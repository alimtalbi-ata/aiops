"""Isolated candidate-kit tests: no Docker, network, production, or real evidence."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from deploy import single_portal_candidate_kit as kit

COMMIT = "a" * 40


class CandidateKitTests(unittest.TestCase):
    def fixture(self, root):
        names = sorted(kit.APPROVED)
        for name in names:
            file = root / name
            file.parent.mkdir(parents=True, exist_ok=True)
            if name == "demo/noc_platform_registry.py":
                components = tuple((f"svc-{n}", f"Service {n}", f"/service/{n}", "engine")
                                   for n in range(20))
                file.write_text("COMPONENTS=" + repr(components) + "\n", encoding="utf-8")
            else:
                file.write_text("# synthetic source fixture\n", encoding="utf-8")
        return names

    def test_deterministic_cumulative_candidate_and_route_denial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            names = self.fixture(root)
            with patch.object(kit, "source_paths", return_value=(COMMIT, names)):
                first = root.parent / "first.zip"
                second = root.parent / "second.zip"
                a = kit.build(root, first, COMMIT)
                b = kit.build(root, second, COMMIT)
            self.assertEqual(a["sha256"], b["sha256"])
            self.assertEqual(a["routes"], 20)
            self.assertFalse(a["production_qualified"])
            with zipfile.ZipFile(first) as z:
                manifest = json.loads(z.read("metadata/source-manifest.json"))
                routes = json.loads(z.read("metadata/planned-routes.json"))
                self.assertEqual(manifest["commit"], COMMIT)
                self.assertEqual(manifest["embedded_count"], len(kit.APPROVED))
                self.assertTrue(all(not row["route_mounted"] and
                                    not row["runtime_authenticated"]
                                    for row in routes["routes"]))
                self.assertIn("NO PRODUCTION DEPLOYMENT", z.read("metadata/README.md").decode())
                self.assertIn("metadata/planned-routes.json", z.read("metadata/SHA256SUMS").decode())

    def test_reject_missing_approved_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            names = self.fixture(root)
            names.remove(kit.APPROVED[0])
            with patch.object(kit, "source_paths", return_value=(COMMIT, names)):
                with self.assertRaisesRegex(ValueError, "approved source missing"):
                    kit.build(root, root.parent / "missing.zip", COMMIT)

    def test_reject_secret_and_leave_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            names = self.fixture(root)
            (root / kit.APPROVED[0]).write_bytes(b"-----BEGIN PRIVATE KEY-----\nsecret")
            output = root.parent / "sensitive.zip"
            with patch.object(kit, "source_paths", return_value=(COMMIT, names)):
                with self.assertRaisesRegex(ValueError, "sensitive"):
                    kit.build(root, output, COMMIT)
            self.assertFalse(output.exists())

    def test_reject_wrong_pin_and_existing_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            names = self.fixture(root)
            output = root.parent / "existing.zip"
            output.write_bytes(b"do-not-overwrite")
            with patch.object(kit, "source_paths", return_value=(COMMIT, names)):
                with self.assertRaisesRegex(ValueError, "already exists"):
                    kit.build(root, output, COMMIT)
                with self.assertRaisesRegex(ValueError, "pinned commit mismatch"):
                    kit.build(root, root.parent / "new.zip", "b" * 40)
            self.assertEqual(output.read_bytes(), b"do-not-overwrite")

    def test_reject_symlink_and_unsafe_path(self):
        self.assertFalse(kit.safe_path("docs/../secrets/key.py"))
        self.assertFalse(kit.safe_path("reports/capture.png"))
        self.assertFalse(kit.safe_path("docs/.env.production"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            names = self.fixture(root)
            path = root / kit.APPROVED[0]
            path.unlink()
            path.symlink_to(root / kit.APPROVED[1])
            with patch.object(kit, "source_paths", return_value=(COMMIT, names)):
                with self.assertRaisesRegex(ValueError, "unsafe tracked source"):
                    kit.build(root, root.parent / "symlink.zip", COMMIT)


if __name__ == "__main__":
    unittest.main()
