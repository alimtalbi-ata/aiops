import datetime as dt
import importlib.util
import json
from pathlib import Path
import unittest

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "acme"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

P = Path(__file__).resolve().parents[1] / "scripts/acme_demo_readiness.py"
spec = importlib.util.spec_from_file_location("acme_demo_readiness", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
NOW = dt.datetime(2026, 11, 16, 17, 0, tzinfo=dt.timezone.utc)


class Readiness(unittest.TestCase):
    def test_pass_is_simulation_only(self):
        result = m.assess(load("valid.json"), NOW)
        self.assertEqual(result["verdict"], "GO_SIMULATION_ONLY")
        self.assertEqual(result["live"], "NO_GO")

    def test_wrong_terminal_reason(self):
        self.assertEqual(m.assess(load("wrong_reason.json"), NOW)["verdict"], "NO_GO")

    def test_real_ticket_identifier_refused(self):
        self.assertEqual(m.assess(load("real_ticket.json"), NOW)["verdict"], "NO_GO")

    def test_non_simulated_approval_identifier_refused(self):
        self.assertEqual(m.assess(load("real_approval.json"), NOW)["verdict"], "NO_GO")

    def test_missing_attempt_identifier(self):
        self.assertEqual(m.assess(load("missing_attempt_id.json"), NOW)["verdict"], "NO_GO")

    def test_malformed_attempt_identifier(self):
        self.assertEqual(m.assess(load("malformed_attempt_id.json"), NOW)["verdict"], "NO_GO")

    def test_missing_receipt(self):
        self.assertEqual(m.assess(None, NOW)["verdict"], "NO_GO")

    def test_no_live_claim(self):
        self.assertEqual(m.assess(load("live_effects.json"), NOW)["verdict"], "NO_GO")

    def test_no_real_glpi(self):
        self.assertEqual(m.assess(load("real_glpi.json"), NOW)["verdict"], "NO_GO")

    def test_no_fake_human(self):
        self.assertEqual(m.assess(load("fake_human.json"), NOW)["verdict"], "NO_GO")

    def test_no_host_mutation(self):
        self.assertEqual(m.assess(load("docker_mutation.json"), NOW)["verdict"], "NO_GO")

    def test_missing_twin_capability_blocks(self):
        self.assertEqual(m.assess(load("missing_twin.json"), NOW)["verdict"], "NO_GO")

    def test_failed_worker_receipt_blocks(self):
        self.assertEqual(m.assess(load("failed_worker.json"), NOW)["verdict"], "NO_GO")

    def test_missing_stage(self):
        self.assertEqual(m.assess(load("empty_stages.json"), NOW)["verdict"], "NO_GO")

    def test_missing_id(self):
        self.assertEqual(m.assess(load("missing_ticket_id.json"), NOW)["verdict"], "NO_GO")

    def test_stale(self):
        self.assertEqual(m.assess(load("stale.json"), NOW)["verdict"], "NO_GO")

    def test_future(self):
        self.assertEqual(m.assess(load("future.json"), NOW)["verdict"], "NO_GO")

    def test_no_pass_on_boolean_zero(self):
        self.assertEqual(m.assess(load("boolean_zero.json"), NOW)["verdict"], "NO_GO")

    def test_unknown_receipt_field_is_rejected(self):
        r = load("valid.json")
        r["unexpected_runtime_claim"] = "PASS"
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_unknown_identifier_field_is_rejected(self):
        r = load("valid.json")
        r["ids"]["unexpected"] = "OTHER"
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_whitespace_only_identifier_is_rejected(self):
        r = load("valid.json")
        r["ids"]["run_id"] = "  "
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_timestamp_must_include_timezone(self):
        r = load("valid.json")
        r["collected_at"] = "2026-11-16T16:55:00"
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

if __name__ == "__main__":
    unittest.main()
