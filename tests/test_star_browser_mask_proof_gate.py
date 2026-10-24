"""V2.13.55: isolated Chromium proof-visibility fence; no HTTP/runtime access."""
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from demo.star_snapshot_browser import CapturePlan, capture, validate_plan

RUN = "RUN-ACME-SYNTHETIC-055"
CORR = "CORR-ACME-SYNTHETIC-055"
EVENT = "EXEC-055"
ORIGIN = "http://127.0.0.1:5678"
HTML = f"""<html><body><div id='proof'>
<span id='run'>{RUN}</span><span id='correlation'>{CORR}</span>
<span id='event'>{EVENT}</span><span id='state'>completed</span>
</div><div id='private'>SYNTHETIC PRIVATE DATA</div></body></html>"""


def plan():
    return CapturePlan(
        cue="correlate", run_id=RUN, correlation_id=CORR, event_ref=EVENT,
        url=ORIGIN + "/workflow/wf055/executions/" + EVENT,
        expected_state="completed", identity_selector="#run",
        event_selector="#event", state_selector="#state",
        redact_selectors=("#private",), allowed_origin=ORIGIN,
        environment="ISOLATED_TEST_FIXTURE", correlation_selector="#correlation",
    )


class MaskProofGateTests(unittest.TestCase):
    def test_same_selector_as_required_identity_or_state_rejected_before_browser(self):
        for selector in ("#run", "#correlation", "#event", "#state"):
            with self.subTest(selector=selector), self.assertRaisesRegex(ValueError, "redaction overlaps"):
                validate_plan(replace(plan(), redact_selectors=(selector,)))

    def test_ambiguous_proof_selectors_rejected_before_browser(self):
        with self.assertRaisesRegex(ValueError, "redaction overlaps"):
            validate_plan(replace(plan(), correlation_selector="#run"))

    def test_ancestor_mask_cannot_conceal_identity_or_observed_state(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"AIOPS_STAR_NO_RUNTIME": "1"}):
            for mask in ("#proof", "body", "html"):
                with self.subTest(mask=mask), self.assertRaisesRegex(ValueError, "conceals checkpoint proof"):
                    capture(replace(plan(), redact_selectors=(mask,)), Path(tmp),
                            approved_read=True, fixture_html=HTML)
                self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_disjoint_mask_still_captures_synthetic_fixture(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"AIOPS_STAR_NO_RUNTIME": "1"}):
            result = capture(plan(), Path(tmp), approved_read=True, fixture_html=HTML)
            self.assertEqual(result["result"], "CAPTURED_UNREVIEWED")
            manifest = json.loads((Path(tmp) / result["manifest"]).read_text())
            self.assertEqual(manifest["capture_transport"], "LOCAL_HTML_FIXTURE_NO_HTTP")
            self.assertFalse(manifest["runtime_page_authenticated"])
            self.assertFalse(manifest["business_outcome_verified"])
            self.assertEqual(len(list(Path(tmp).glob("*.png"))), 1)


if __name__ == "__main__":
    unittest.main()
