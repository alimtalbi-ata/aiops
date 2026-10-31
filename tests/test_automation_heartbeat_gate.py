import datetime as dt
import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "automation_heartbeat_gate.py"
spec = importlib.util.spec_from_file_location("automation_heartbeat_gate", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NOW = dt.datetime(2026, 10, 31, 20, 11, tzinfo=dt.timezone.utc)


def item(**changes):
    d = dict(plane="chatgpt", id="1/5", enabled=True, state="OBSERVED",
             cadence_seconds=3600, last_success_at="2026-10-31T19:30:00Z",
             next_run_at="2026-10-31T21:30:00Z", evidence_ref="https://example.invalid/receipt")
    d.update(changes)
    return d


def snapshot(*entries):
    return dict(schema_version="aiops.automation-heartbeat.v1", entries=list(entries))


class GateTests(unittest.TestCase):
    def test_recent_hourly_success(self):
        self.assertEqual(module.evaluate(snapshot(item()), NOW)["overall"], "PASS")

    def test_missing_next_run_is_unknown_not_success(self):
        r = module.evaluate(snapshot(item(next_run_at=None)), NOW)
        self.assertEqual(r["overall"], "WARN")
        self.assertIn("NEXT_UNKNOWN", r["entries"][0]["signals"])

    def test_missed_run_fails(self):
        r = module.evaluate(snapshot(item(last_success_at="2026-10-31T18:00:00Z")), NOW)
        self.assertEqual(r["overall"], "FAIL")
        self.assertIn("MISSED_RUN", r["entries"][0]["signals"])

    def test_debian_unattested_is_not_healthy(self):
        r = module.evaluate(snapshot(item(plane="debian", id="srv-cron", enabled=None,
                                         state="UNATTESTED", last_success_at=None,
                                         next_run_at=None, evidence_ref=None)), NOW)
        self.assertEqual(r["overall"], "WARN")
        self.assertIn("UNATTESTED", r["entries"][0]["signals"])

    def test_lab_cannot_be_runtime_attestation(self):
        r = module.evaluate(snapshot(item(plane="lab", id="acme", state="SYNTHETIC")), NOW)
        self.assertEqual(r["overall"], "PASS")
        self.assertEqual(r["entries"][0]["plane"], "lab")

    def test_lab_unknown_provenance(self):
        r = module.evaluate(snapshot(item(plane="lab", id="acme", state="OBSERVED")), NOW)
        self.assertIn("LAB_PROVENANCE_UNKNOWN", r["entries"][0]["signals"])

    def test_duplicate_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            module.evaluate(snapshot(item(), item()), NOW)

    def test_naive_timestamp_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            module.evaluate(snapshot(item(last_success_at="2026-10-31T19:30:00")), NOW)

    def test_future_timestamp_fails(self):
        r = module.evaluate(snapshot(item(last_success_at="2026-10-31T22:00:00Z")), NOW)
        self.assertIn("CLOCK_SKEW", r["entries"][0]["signals"])

    def test_inactive_schedule_not_claimed(self):
        r = module.evaluate(snapshot(item(enabled=False)), NOW)
        self.assertEqual(r["overall"], "WARN")
        self.assertIn("INACTIVE", r["entries"][0]["signals"])

    def test_event_driven_github_does_not_require_next(self):
        r = module.evaluate(snapshot(item(plane="github", id="quality", cadence_seconds=None,
                                          next_run_at=None)), NOW)
        self.assertEqual(r["overall"], "PASS")

    def test_receipt_digest_verified_and_tamper_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "receipt.json"
            p.write_text('{"exit_code":0}')
            sha = hashlib.sha256(p.read_bytes()).hexdigest()
            healthy = module.evaluate(snapshot(item(receipt_path=str(p), receipt_sha256=sha)), NOW)
            self.assertEqual(healthy["overall"], "PASS")
            p.write_text('{"exit_code":1}')
            tampered = module.evaluate(snapshot(item(receipt_path=str(p), receipt_sha256=sha)), NOW)
            self.assertEqual(tampered["overall"], "FAIL")
            self.assertIn("RECEIPT_HASH_MISMATCH", tampered["entries"][0]["signals"])

    def test_cli_exit_status(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "evidence.json"
            path.write_text(json.dumps(snapshot(item(next_run_at=None))))
            proc = subprocess.run([sys.executable, str(SCRIPT), "--input", str(path),
                                   "--now", "2026-10-31T20:11:00Z"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(json.loads(proc.stdout)["overall"], "WARN")


if __name__ == "__main__":
    unittest.main()
