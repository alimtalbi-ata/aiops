"""V2.13.58: Chromium synthetic regression for CSS paint-suppressed proof."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from demo.star_snapshot_browser import CapturePlan, capture

RUN = "RUN-ACME-SYNTHETIC-058"
CORR = "CORR-ACME-SYNTHETIC-058"
EVENT = "EXEC-058"
ORIGIN = "http://127.0.0.1:5678"
HTML = f"""<html><body><div id='proof'>
<span id='run'>{RUN}</span><span id='correlation'>{CORR}</span>
<span id='event'>{EVENT}</span><span id='state'>completed</span>
</div><div id='private'>SYNTHETIC PRIVATE DATA</div></body></html>"""


def plan():
    return CapturePlan(
        cue="correlate", run_id=RUN, correlation_id=CORR, event_ref=EVENT,
        url=ORIGIN + "/workflow/wf058/executions/" + EVENT,
        expected_state="completed", identity_selector="#run",
        event_selector="#event", state_selector="#state",
        redact_selectors=("#private",), allowed_origin=ORIGIN,
        environment="ISOLATED_TEST_FIXTURE", correlation_selector="#correlation",
    )


class CSSProofVisibilityTests(unittest.TestCase):
    def _rejected(self, html):
        with tempfile.TemporaryDirectory() as td, patch.dict("os.environ", {"AIOPS_STAR_NO_RUNTIME": "1"}):
            with self.assertRaisesRegex(ValueError, "visually hidden checkpoint proof"):
                capture(plan(), Path(td), approved_read=True, fixture_html=html)
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_css_filter_opacity_zero_on_ancestor(self):
        self._rejected(HTML.replace("id='proof'", "id='proof' style='filter:opacity(0)'"))

    def test_clip_path_hides_event(self):
        self._rejected(HTML.replace("id='event'", "id='event' style='clip-path:inset(50%)'"))

    def test_webkit_text_fill_transparent(self):
        self._rejected(HTML.replace("id='state'", "id='state' style='-webkit-text-fill-color:transparent'"))

    def test_mask_image_hides_run(self):
        self._rejected(HTML.replace("id='run'", "id='run' style='mask-image:linear-gradient(transparent,transparent)'"))

    def test_visible_fixture_still_succeeds(self):
        with tempfile.TemporaryDirectory() as td, patch.dict("os.environ", {"AIOPS_STAR_NO_RUNTIME": "1"}):
            result = capture(plan(), Path(td), approved_read=True, fixture_html=HTML)
            self.assertEqual(result["result"], "CAPTURED_UNREVIEWED")
            data = json.loads((Path(td) / result["manifest"]).read_text())
            self.assertEqual(data["provenance"], "ISOLATED_TEST_FIXTURE")
            self.assertFalse(data["runtime_page_authenticated"])


if __name__ == "__main__":
    unittest.main()
