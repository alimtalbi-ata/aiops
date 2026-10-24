"""Synthetic offline and Chromium fixture tests; no live application requests."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from demo.star_checkpoint_plan_builder import build_star_capture_plans
from demo.star_snapshot_browser import capture
from demo.star_snapshot_choreography import CUES


def spec():
    result = {
        "run_id": "RUN-STAR-TEST-054", "correlation_id": "CORR-STAR-TEST-054",
        "environment": "ISOLATED_TEST_FIXTURE",
        "origins": {"grafana": "http://127.0.0.1:3000", "n8n": "http://127.0.0.1:5678",
                    "glpi": "http://127.0.0.1:8080"},
        "checkpoints": {},
    }
    for index, cue in enumerate(CUES):
        ref = str(100 + index) if cue.service != "grafana" else "uid" + str(index)
        route = ({"workflow_id": "wf" + str(index)} if cue.service == "n8n" else
                 {"slug": "acme", "from_ms": 1792800000000 + index * 1000,
                  "to_ms": 1792800060000 + index * 1000} if cue.service == "grafana" else {})
        result["checkpoints"][cue.cue] = {
            "event_ref": ref, "route": route,
            "selectors": {"run": "#run", "correlation": "#correlation", "event": "#event",
                          "state": "#state", "redact": ["#private"]},
        }
    return result


class CheckpointPlanTests(unittest.TestCase):
    def test_nine_plans_exact_app_ports_and_dry_run(self):
        plans = build_star_capture_plans(spec())
        self.assertEqual([p.cue for p in plans], [c.cue for c in CUES])
        self.assertEqual(len(plans), 9)
        for plan in plans:
            result = capture(plan, Path("/nonexistent"))
            self.assertEqual(result["result"], "DRY_RUN")
            self.assertFalse(result["runtime_authenticated"])
            self.assertFalse(plan.approved_get_urls)
        self.assertIn("/front/ticket.form.php?id=", plans[4].url)
        self.assertIn("/executions/", plans[1].url)
        self.assertIn("var-run_id=RUN-STAR-TEST-054", plans[0].url)

    def test_fail_closed_missing_and_unexpected_identity(self):
        for field in ("run_id", "correlation_id"):
            data = spec(); data[field] = ""
            with self.subTest(field=field), self.assertRaises(ValueError):
                build_star_capture_plans(data)
        data = spec(); del data["checkpoints"]["analyze"]
        with self.assertRaises(ValueError): build_star_capture_plans(data)
        data = spec(); data["checkpoints"]["detect"]["event_ref"] = ""
        with self.assertRaises(ValueError): build_star_capture_plans(data)
        data = spec(); data["checkpoints"]["detect"]["runtime_authenticated"] = True
        with self.assertRaises(ValueError): build_star_capture_plans(data)

    def test_wrong_legacy_ports_and_unsafe_origins(self):
        for app, origin in (("glpi", "http://127.0.0.1:18080"),
                            ("n8n", "http://127.0.0.1:8080"),
                            ("grafana", "http://127.0.0.1:3001"),
                            ("grafana", "http://admin:secret@127.0.0.1:3000"),
                            ("glpi", "http://127.0.0.1:8080/evil"),
                            ("glpi", "http://evil.example:8080")):
            data = spec(); data["origins"][app] = origin
            with self.subTest(app=app, origin=origin), self.assertRaises(ValueError):
                build_star_capture_plans(data)

    def test_n8n_execution_reuse_or_absence_rejected(self):
        data = spec()
        data["checkpoints"]["enrich"]["event_ref"] = data["checkpoints"]["correlate"]["event_ref"]
        with self.assertRaises(ValueError): build_star_capture_plans(data)
        data = spec(); data["checkpoints"]["correlate"]["route"] = {"workflow_id": ""}
        with self.assertRaises(ValueError): build_star_capture_plans(data)

    def test_bad_grafana_time_window_and_slug(self):
        for update in ({"to_ms": 1792800000000}, {"from_ms": 0},
                       {"slug": "../escape"}, {"to_ms": 1792900000000}):
            data = spec(); data["checkpoints"]["detect"]["route"].update(update)
            with self.subTest(update=update), self.assertRaises(ValueError):
                build_star_capture_plans(data)

    def test_glpi_ticket_id_and_mask_required(self):
        data = spec(); data["checkpoints"]["ticket"]["event_ref"] = "TICKET-99"
        with self.assertRaises(ValueError): build_star_capture_plans(data)
        data = spec(); data["checkpoints"]["ticket"]["selectors"]["redact"] = []
        with self.assertRaises(ValueError): build_star_capture_plans(data)

    def test_operator_plan_does_not_enable_browsing(self):
        data = spec(); data["environment"] = "OPERATOR_BROWSER_UNREVIEWED"
        plans = build_star_capture_plans(data)
        self.assertEqual(len(plans), 9)
        with patch.dict(os.environ, {"AIOPS_STAR_NO_RUNTIME": "1"}):
            with self.assertRaises(ValueError):
                capture(plans[0], Path("/nonexistent"), approved_read=True)

    def test_isolated_chromium_dom_and_mask_if_available(self):
        plan = build_star_capture_plans(spec())[0]
        html = ("<html><body><span id='run'>" + plan.run_id + "</span>"
                "<span id='correlation'>" + plan.correlation_id + "</span>"
                "<span id='event'>" + plan.event_ref + "</span>"
                "<span id='state'>" + plan.expected_state + "</span>"
                "<span id='private'>SYNTHETIC-SECRET-TO-MASK</span></body></html>")
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"AIOPS_STAR_NO_RUNTIME": "1"}):
            try:
                result = capture(plan, Path(temp), approved_read=True, fixture_html=html)
            except Exception as exc:
                if "Executable doesn't exist" in str(exc):
                    self.skipTest("Chromium not installed")
                raise
            self.assertEqual(result["result"], "CAPTURED_UNREVIEWED")
            self.assertFalse(result["runtime_authenticated"])
            self.assertEqual(len(list(Path(temp).glob("*.png"))), 1)
            self.assertEqual(len(list(Path(temp).glob("*.json"))), 1)
            self.assertIn("LOCAL_HTML_FIXTURE_NO_HTTP", next(Path(temp).glob("*.json")).read_text())


if __name__ == "__main__":
    unittest.main()
