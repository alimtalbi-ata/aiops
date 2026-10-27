import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from demo.evidence_publish import publish_capture_set

SERVICES = ("portal", "thruk", "grafana", "n8n", "glpi")


class EvidencePublishTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.staging, self.output = root / "stage", root / "out"
        self.staging.mkdir(mode=0o700)
        self.output.mkdir(mode=0o700)
        for name in [*(service + ".png" for service in SERVICES), "manifest.json"]:
            (self.staging / name).write_bytes(b"offline test fixture")

    def test_success_manifest_published_last(self):
        order = []
        real_link = os.link
        def recording_link(source, target):
            order.append(Path(target).name)
            return real_link(source, target)
        with patch("demo.evidence_publish.os.link", side_effect=recording_link):
            publish_capture_set(self.staging, self.output, SERVICES)
        self.assertEqual(order, [*(s + ".png" for s in SERVICES), "manifest.json"])
        self.assertEqual(len(list(self.output.iterdir())), 6)

    def test_failed_third_link_rolls_back_all_created_files(self):
        real_link = os.link
        count = 0
        def failing_link(source, target):
            nonlocal count
            count += 1
            if count == 3:
                raise OSError("injected filesystem failure")
            return real_link(source, target)
        with patch("demo.evidence_publish.os.link", side_effect=failing_link):
            with self.assertRaisesRegex(OSError, "injected"):
                publish_capture_set(self.staging, self.output, SERVICES)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_existing_file_is_preserved_and_no_publication(self):
        existing = self.output / "grafana.png"
        existing.write_bytes(b"original")
        with self.assertRaisesRegex(ValueError, "overwrite"):
            publish_capture_set(self.staging, self.output, SERVICES)
        self.assertEqual(existing.read_bytes(), b"original")
        self.assertEqual(len(list(self.output.iterdir())), 1)

    def test_missing_manifest_fails_before_publication(self):
        (self.staging / "manifest.json").unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            publish_capture_set(self.staging, self.output, SERVICES)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_symlinked_staged_capture_rejected(self):
        victim = self.staging / "portal.png"
        victim.unlink()
        victim.symlink_to(self.staging / "thruk.png")
        with self.assertRaisesRegex(ValueError, "symlinked"):
            publish_capture_set(self.staging, self.output, SERVICES)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_duplicate_service_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid"):
            publish_capture_set(self.staging, self.output, ("portal", "portal"))

    def test_path_traversal_service_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid"):
            publish_capture_set(self.staging, self.output, ("../portal",))


if __name__ == "__main__":
    unittest.main()
