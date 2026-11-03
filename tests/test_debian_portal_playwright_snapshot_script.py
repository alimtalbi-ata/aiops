"""Contract for host-only Playwright snapshot CLI (no network, no browser)."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

FILE = Path(__file__).resolve().parents[1] / "deploy" / "debian-portal-playwright-snapshot.py"
spec = importlib.util.spec_from_file_location("host_portal_playwright_snapshot", FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class HostPlaywrightSnapshotContracts(unittest.TestCase):
    def test_https_reviewed_and_loopback_http_only(self):
        self.assertEqual(module.verify_base_url("http://127.0.0.1:7777/"),
                         "http://127.0.0.1:7777")
        self.assertEqual(module.verify_base_url("https://portal.example.test:7777/"),
                         "https://portal.example.test:7777")
        for invalid in (
            "http://10.79.94.202:7777", "http://example.com:7777",
            "http://127.0.0.1:7777/?token=abc",
            "http://foo:bar@127.0.0.1:7777", "file:///etc/passwd",
            "https://portal.example.test:7777/#runs",
            "https://portal.example.test", "",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                module.verify_base_url(invalid)

    def test_receipt_is_local_mode_0600_with_no_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "snapshots"
            module.secure_dir(target)
            payload = {
                "schema": "aiops.portal-host-playwright-snapshots.v1",
                "status": "PASS_ANONYMOUS_SYNTHETIC_BROWSER_ONLY",
                "screenshots": [], "live_effects": 0,
                "human_glpi_acl": "NOT_VERIFIED",
            }
            module.save_receipt(target, payload)
            file = target / "portal-playwright-receipt.json"
            self.assertEqual(json.loads(file.read_text()), payload)
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
            self.assertEqual(target.stat().st_mode & 0o777, 0o700)

    def test_symlink_output_refused(self):
        with tempfile.TemporaryDirectory() as d:
            parent = Path(d)
            target = parent / "real"
            target.mkdir()
            link = parent / "link"
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaises(OSError):
                module.secure_dir(link)

    def test_capture_hashes_bytes_and_does_not_store_video(self):
        class DummyPage:
            viewport_size = {"width": 1280, "height": 720}
            def screenshot(self, *, full_page, animations):
                self.last = (full_page, animations)
                return b"PNG_SYNTHETIC_TEST_ONLY"
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / "snapshots"
            folder.mkdir(mode=0o700)
            record = {"screenshots": []}
            page = DummyPage()
            module.capture(page, folder, "01-overview", record)
            shot = folder / "01-overview.png"
            self.assertEqual(shot.stat().st_mode & 0o777, 0o600)
            self.assertEqual(record["screenshots"][0]["name"], shot.name)
            self.assertEqual(record["screenshots"][0]["bytes"], len(b"PNG_SYNTHETIC_TEST_ONLY"))
            self.assertEqual(page.last, (True, "disabled"))
            with self.assertRaises(ValueError):
                module.capture(page, folder, "../private", record)
            # A pre-existing symlink must be replaced, not followed. This
            # protects files outside the private screenshot directory.
            outside = Path(d) / "outside.txt"
            outside.write_text("DO_NOT_OVERWRITE")
            shot.unlink()
            shot.symlink_to(outside)
            module.capture(page, folder, "01-overview", record)
            self.assertEqual(outside.read_text(), "DO_NOT_OVERWRITE")
            self.assertFalse(shot.is_symlink())
            self.assertEqual(shot.stat().st_mode & 0o777, 0o600)
            self.assertEqual(shot.read_bytes(), b"PNG_SYNTHETIC_TEST_ONLY")
            self.assertEqual(list(folder.glob(".shot-*.png")), [])

    def test_capture_failure_leaves_no_partial_screenshot(self):
        class FailingPage:
            viewport_size = {"width": 390, "height": 844}
            def screenshot(self, *, full_page, animations):
                raise RuntimeError("browser crashed")
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            with self.assertRaises(RuntimeError):
                module.capture(FailingPage(), folder, "09-mobile-overview",
                               {"screenshots": []})
            self.assertEqual(list(folder.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
