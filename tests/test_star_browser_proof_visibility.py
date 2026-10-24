"""V2.13.57: Chromium fixture must not accept visually invisible DOM proof."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_star_browser_mask_proof_gate import HTML, plan
from demo.star_snapshot_browser import capture


class ProofVisibilityTests(unittest.TestCase):
    def _capture(self, html):
        with tempfile.TemporaryDirectory() as td, patch.dict("os.environ", {"AIOPS_STAR_NO_RUNTIME": "1"}):
            output = Path(td)
            with self.assertRaisesRegex(ValueError, "visually hidden checkpoint proof"):
                capture(plan(), output, approved_read=True, fixture_html=html)
            self.assertEqual(list(output.iterdir()), [], "rejected capture must leave no evidence")

    def test_identity_with_css_opacity_zero_fails_closed(self):
        self._capture(HTML.replace("id='run'", "id='run' style='opacity:0'"))

    def test_ancestor_opacity_zero_fails_closed(self):
        self._capture(HTML.replace("id='proof'", "id='proof' style='opacity:0'"))

    def test_transparent_observed_state_fails_closed(self):
        self._capture(HTML.replace("id='state'", "id='state' style='color:transparent'"))

    def test_zero_font_size_already_fails_closed(self):
        with tempfile.TemporaryDirectory() as td, patch.dict("os.environ", {"AIOPS_STAR_NO_RUNTIME": "1"}):
            output = Path(td)
            with self.assertRaises(ValueError):
                capture(plan(), output, approved_read=True,
                        fixture_html=HTML.replace("id='event'", "id='event' style='font-size:0'"))
            self.assertEqual(list(output.iterdir()), [])

    def test_normal_visible_fixture_still_creates_unreviewed_manifest(self):
        with tempfile.TemporaryDirectory() as td, patch.dict("os.environ", {"AIOPS_STAR_NO_RUNTIME": "1"}):
            output = Path(td)
            result = capture(plan(), output, approved_read=True, fixture_html=HTML)
            self.assertEqual(result["result"], "CAPTURED_UNREVIEWED")
            manifest = json.loads((output / result["manifest"]).read_text())
            self.assertEqual(manifest["provenance"], "ISOLATED_TEST_FIXTURE")
            self.assertFalse(manifest["runtime_page_authenticated"])


if __name__ == "__main__":
    unittest.main()
