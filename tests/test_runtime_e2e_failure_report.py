"""Offline contract tests for the actual runtime-e2e shell report generator.

No Docker, DB, Temporal, network, or production environment is touched.
"""
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tests" / "runtime-e2e.sh"


def report_generator():
    text = SCRIPT.read_text(encoding="utf-8")
    match = re.search(r"python3 - <<'PY'\n(.*?)\nPY\n", text, re.S)
    if not match:
        raise AssertionError("runtime-e2e reporter heredoc missing")
    return text, match.group(1)


class RuntimeE2EFailureReportTests(unittest.TestCase):
    def _run_report(self, *, last_stage="OBSERVE", last_type="STAGE_STARTED"):
        _, code = report_generator()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "reports").mkdir()
            env = dict(os.environ)
            env.update({
                "RESULT": "FAIL",
                "FAILURE": "expected_synthetic_run_resolved_without_effects_but_status_BLOCKED",
                "RUN_ID": "RUN-ACME-TEST-041", "RUN_STATUS": "BLOCKED",
                "ANALYSIS_COUNT": "2", "CRITIQUE_COUNT": "1", "POLICY_COUNT": "0",
                "EVIDENCE_COUNT": "3", "EFFECT_COUNT": "0", "EVENT_COUNT": "4",
                "LAST_EVENT_STAGE": last_stage, "LAST_EVENT_TYPE": last_type,
                "EVENT_TYPES": "RUN_CREATED,STAGE_STARTED,secret:password,STAGE_COMPLETED",
            })
            proc = subprocess.run(["python3", "-c", code], cwd=tmp, env=env,
                                  text=True, capture_output=True, timeout=8, check=True)
            report_path = Path(tmp) / "reports" / "runtime-e2e-RUN-ACME-TEST-041.json"
            self.assertTrue(report_path.is_file(), proc.stdout)
            return json.loads(report_path.read_text(encoding="utf-8"))

    def test_blocked_report_keeps_real_counts_and_terminal_event(self):
        report = self._run_report()
        self.assertEqual(report["result"], "FAIL")
        self.assertEqual(report["run_status"], "BLOCKED")
        self.assertEqual(report["analysis_records"], 2)
        self.assertEqual(report["critique_records"], 1)
        self.assertEqual(report["run_evidence_records"], 3)
        self.assertEqual(report["event_count"], 4)
        self.assertEqual(report["last_event_stage"], "OBSERVE")
        self.assertEqual(report["last_event_type"], "STAGE_STARTED")
        self.assertEqual(report["effect_receipts"], 0)
        self.assertEqual(report["live_execution"], "disabled")

    def test_untrusted_labels_are_not_leaked(self):
        report = self._run_report(last_stage="OBSERVE\nBearer SECRET", last_type="GET /token")
        self.assertEqual(report["last_event_stage"], "REDACTED")
        self.assertEqual(report["last_event_type"], "REDACTED")
        self.assertEqual(report["event_types"], ["RUN_CREATED", "STAGE_STARTED", "STAGE_COMPLETED"])
        self.assertNotIn("SECRET", json.dumps(report))
        self.assertNotIn("password", json.dumps(report))

    def test_status_gate_is_after_diagnostic_queries(self):
        script, _ = report_generator()
        self.assertLess(script.index('EVENT_COUNT="$(psqlc'),
                        script.index('[[ "$RUN_STATUS" == "RESOLVED" ]]'))
        self.assertLess(script.index('ANALYSIS_COUNT="$(psqlc'),
                        script.index('[[ "$RUN_STATUS" == "RESOLVED" ]]'))
        self.assertLess(script.index('EVENT_TYPES="$(psqlc'),
                        script.index('[[ "$RUN_STATUS" == "RESOLVED" ]]'))
        self.assertIn('trap write_report EXIT', script)
        self.assertNotIn('docker compose down', script)


if __name__ == "__main__":
    unittest.main()
