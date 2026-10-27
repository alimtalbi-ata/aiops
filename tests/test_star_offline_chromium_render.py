"""Actual Playwright Chromium smoke test on strictly local synthetic HTML."""
import asyncio
import hashlib
import tempfile
import unittest
from pathlib import Path

from demo.star_offline_chromium_fixture import render_isolated_fixtures
from demo.star_png_integrity import inspect_png

class OfflineChromiumRenderTest(unittest.TestCase):
    def test_real_chromium_produces_integrity_checked_synthetic_png(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixtures = root / "fixtures"
            fixtures.mkdir()
            (fixtures / "detect.html").write_text(
                "<!doctype html><html><head><title>Synthetic test</title></head>"
                "<body><h1>TEST FIXTURE — NOT A RUNTIME EVIDENCE</h1></body></html>",
                encoding="utf-8")
            plan = {
                "schema":"star-browser-capture-tasks-v1",
                "run_id":"RUN-TEST-123",
                "browser_executed":False, "runtime_proof_count":0,
                "live_action_authorized":False,
                "tasks":[{"cue":"detect","capture_performed":False,
                          "authenticated_runtime_proof":False}]
            }
            result = asyncio.run(render_isolated_fixtures(
                plan, {"detect":"detect.html"}, fixtures, root / "screenshots"))
            self.assertEqual(result["runtime_proof_count"], 0)
            self.assertFalse(result["live_action_authorized"])
            self.assertEqual(len(result["captures"]), 1)
            record = result["captures"][0]
            self.assertEqual(record["origin"], "SYNTHETIC_LOCAL_FIXTURE")
            self.assertFalse(record["runtime_authenticated"])
            digest, size = inspect_png(root / "screenshots" / "detect.png")
            self.assertEqual(digest, record["sha256"])
            self.assertGreater(size, 100)
            self.assertTrue((root / "screenshots" / "manifest.json").exists())

if __name__ == "__main__":
    unittest.main()
