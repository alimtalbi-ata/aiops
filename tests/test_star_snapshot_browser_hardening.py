"""V2.13.39 isolated contract tests; no production access or server mutation."""
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from demo.star_browser_manifest_gate import verify_browser_manifests
from demo.star_snapshot_browser import CapturePlan, capture, load_plan, validate_plan

RUN = "RUN-ACME-TEST-039"
CORR = "CORR-ACME-TEST-039"
EVENT = "EXEC-39"
ORIGIN = "http://127.0.0.1:55677"
HTML = f'''<!doctype html><html><body><div id="run">{RUN}</div>
<div id="corr">{CORR}</div><div id="event">{EVENT}</div>
<div id="state">completed</div><div id="secret">SYNTHETIC PRIVATE DATA</div>
</body></html>'''


def plan():
    return CapturePlan("correlate", RUN, CORR, EVENT, ORIGIN + "/executions/" + EVENT,
                       "completed", "#run", "#event", "#state", ("#secret",),
                       ORIGIN, "ISOLATED_TEST_FIXTURE", "#corr")


class BrowserHardeningTests(unittest.TestCase):
    def test_dry_run_stays_zero_effect_without_opt_in(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"AIOPS_STAR_ALLOW_OPERATOR_READ": "0"}):
                self.assertEqual(capture(plan(), Path(td))["result"], "DRY_RUN")
                self.assertEqual(list(Path(td).iterdir()), [])

    def test_isolated_provenance_cannot_browse_runtime_even_with_operator_opt_in(self):
        # A synthetic plan without local HTML must never silently become an
        # operator HTTP capture, even when the operator opt-in is present.
        # This check runs before Playwright/Chromium and needs no network.
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {
            "AIOPS_STAR_ALLOW_OPERATOR_READ": "1", "AIOPS_STAR_NO_RUNTIME": "0"
        }):
            with self.assertRaisesRegex(ValueError, "isolated fixture requires local HTML"):
                capture(plan(), Path(td), approved_read=True)
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_operator_runtime_requires_separate_opt_in(self):
        p = replace(plan(), environment="OPERATOR_BROWSER_UNREVIEWED")
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"AIOPS_STAR_ALLOW_OPERATOR_READ": "0", "AIOPS_STAR_NO_RUNTIME": "0"}):
            with self.assertRaisesRegex(ValueError, "explicit environment opt-in"):
                capture(p, Path(td), approved_read=True)
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_ci_offline_fence_overrides_runtime_opt_in(self):
        p = replace(plan(), environment="OPERATOR_BROWSER_UNREVIEWED")
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"AIOPS_STAR_ALLOW_OPERATOR_READ": "1", "AIOPS_STAR_NO_RUNTIME": "1"}):
            with self.assertRaisesRegex(ValueError, "runtime browsing disabled"):
                capture(p, Path(td), approved_read=True)

    def test_get_subresources_must_be_explicitly_approved(self):
        p = plan()
        self.assertEqual(validate_plan(p)["mode"], "READ_ONLY_GET")
        allowed = replace(p, approved_get_urls=(ORIGIN + "/assets/view.css",))
        self.assertEqual(validate_plan(allowed)["service"], "n8n")
        for urls in (("https://external.invalid/a.css",),
                     (ORIGIN + "/assets/a.css", ORIGIN + "/assets/a.css"),
                     (p.url,), (ORIGIN + "/assets/a.css#frag",)):
            with self.subTest(urls=urls), self.assertRaises(ValueError):
                validate_plan(replace(p, approved_get_urls=urls))

    def test_unreviewed_fixture_get_fails_even_when_same_origin_allowlisted(self):
        malicious = HTML.replace("</body>",
            f'<script>fetch("{ORIGIN}/assets/view.css").catch(()=>{{}})</script></body>')
        with tempfile.TemporaryDirectory() as td:
            p = replace(plan(), approved_get_urls=(ORIGIN + "/assets/view.css",))
            with self.assertRaises(ValueError):
                capture(p, Path(td), approved_read=True, fixture_html=malicious)
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_fixture_manifest_passes_offline_gate_as_simulated_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = capture(plan(), root, approved_read=True, fixture_html=HTML)
            self.assertEqual(result["result"], "CAPTURED_UNREVIEWED")
            report = verify_browser_manifests(root,
                {"run_id": RUN, "correlation_id": CORR, "events": {"correlate": EVENT}},
                [result["manifest"]])
            self.assertEqual(report["entries"][1]["status"], "simulated")
            self.assertFalse(report["runtime_authenticated"])
            self.assertFalse(report["business_validated"])
            self.assertFalse(report["live_action_authorized"])

    def test_plan_json_duplicate_key_and_oversize_refused(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / "plan.json"
            data = dict(vars(plan()))
            data["redact_selectors"] = list(data["redact_selectors"])
            data.pop("approved_get_urls")  # optional for older local plans
            file.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(load_plan(file).approved_get_urls, ())
            file.write_text('{"run_id":"RUN-AAA","run_id":"RUN-BBB"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_plan(file)
            file.write_text(" " * 17000, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "size limit"):
                load_plan(file)


if __name__ == "__main__":
    unittest.main()
