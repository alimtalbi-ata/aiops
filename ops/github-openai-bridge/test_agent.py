"""Offline contract tests for the Codex-free bridge. Run: python3 -m unittest discover -s ops/github-openai-bridge -p 'test_*.py'"""
import datetime as dt
import importlib.util
import pathlib
import json
from unittest.mock import patch
import tempfile
import unittest

FILE = pathlib.Path(__file__).with_name("agent.py")
spec = importlib.util.spec_from_file_location("aiops_bridge_agent", FILE)
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)
NOW = dt.datetime(2026, 11, 16, 16, 0, tzinfo=dt.timezone.utc)
VALID = "AIOPS2_BRIDGE_V1 status 0123456789abcdef0123456789abcdef 2026-11-16T17:00:00Z"

def comment(body=VALID, login="alimtalbi-ata", url="https://github.com/alimtalbi-ata/aiops/issues/464#issuecomment-12"):
    return {"id": 12, "user": {"login": login}, "html_url": url, "body": body}

class BridgeContract(unittest.TestCase):
    def test_valid_status(self):
        self.assertEqual(agent.parse(comment(), NOW), ("status", "0123456789abcdef0123456789abcdef"))

    def test_acme_receipt_status_authorized(self):
        self.assertEqual(agent.parse(comment(body=VALID.replace("status", "acme_receipt_status")), NOW),
                         ("acme_receipt_status", "0123456789abcdef0123456789abcdef"))

    def test_acme_receipt_status_untrusted_author(self):
        self.assertIsNone(agent.parse(comment(body=VALID.replace("status", "acme_receipt_status"), login="attacker"), NOW))

    def test_acme_receipt_metadata_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(agent, "Path", wraps=pathlib.Path) as mock_path:
                mock_path.return_value = pathlib.Path(directory) / "absent.json"
                self.assertEqual(agent.acme_receipt_status()["status"], "NOT_AVAILABLE")

    def test_acme_receipt_metadata_valid_and_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "receipt.json"
            path.write_text(json.dumps({
                "schema": "aiops.debian-acme-sim-e2e.v1",
                "status": "PASS", "mode": "SIMULATION",
                "tenant_id": "ACME-TEST", "scenario_id": "ACME-SAN-PAYMENTS",
                "approval_issuer": "TWIN_ACME_SIMULATED",
                "human_approval_claimed": False, "docker_mutations": 0,
                "collected_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "live_effects_allowed": False, "real_glpi_writes_allowed": False,
                "ids": {"ticket_id": "SENSITIVE-TEST-IDENTIFIER"}}))
            with patch.object(agent, "Path", return_value=path):
                result = agent.acme_receipt_status()
            self.assertEqual(result["status"], "OBSERVED")
            self.assertEqual(result["e2e_status"], "PASS")
            self.assertTrue(result["sandbox_only"])
            self.assertTrue(result["fresh_60m"])
            self.assertNotIn("SENSITIVE-TEST-IDENTIFIER", json.dumps(result))
            self.assertNotIn("ids", result)

    def test_acme_receipt_metadata_incomplete_is_not_sandbox_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "receipt.json"
            path.write_text(json.dumps({
                "schema": "aiops.debian-acme-sim-e2e.v1",
                "status": "PASS", "mode": "SIMULATION",
                "live_effects_allowed": False, "real_glpi_writes_allowed": False}))
            with patch.object(agent, "Path", return_value=path):
                result = agent.acme_receipt_status()
            self.assertEqual(result["status"], "OBSERVED")
            self.assertFalse(result["sandbox_only"])

    def test_acme_receipt_metadata_stale_is_not_fresh(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "receipt.json"
            path.write_text(json.dumps({
                "schema": "aiops.debian-acme-sim-e2e.v1",
                "status": "PASS", "mode": "SIMULATION",
                "collected_at": "2020-01-01T00:00:00+00:00"}))
            with patch.object(agent, "Path", return_value=path):
                result = agent.acme_receipt_status()
            self.assertFalse(result["fresh_60m"])

    def test_acme_receipt_metadata_future_is_not_fresh(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "receipt.json"
            path.write_text(json.dumps({
                "schema": "aiops.debian-acme-sim-e2e.v1",
                "status": "PASS", "mode": "SIMULATION",
                "collected_at": "2099-01-01T00:00:00+00:00"}))
            with patch.object(agent, "Path", return_value=path):
                result = agent.acme_receipt_status()
            self.assertFalse(result["fresh_60m"])

    def test_acme_receipt_metadata_live_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "receipt.json"
            path.write_text(json.dumps({
                "schema": "aiops.debian-acme-sim-e2e.v1",
                "status": "PASS", "mode": "LIVE",
                "live_effects_allowed": True, "real_glpi_writes_allowed": True}))
            with patch.object(agent, "Path", return_value=path):
                result = agent.acme_receipt_status()
            self.assertFalse(result["sandbox_only"])

    def test_acme_receipt_metadata_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = pathlib.Path(directory) / "private.json"
            target.write_text(json.dumps({"status": "PASS"}))
            link = pathlib.Path(directory) / "receipt.json"
            link.symlink_to(target)
            with patch.object(agent, "Path", return_value=link):
                self.assertEqual(agent.acme_receipt_status()["status"], "NOT_AVAILABLE")

    def test_acme_receipt_metadata_oversized_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "receipt.json"
            path.write_text("x" * 65537)
            with patch.object(agent, "Path", return_value=path):
                self.assertEqual(agent.acme_receipt_status()["status"], "NOT_AVAILABLE")

    def test_acme_receipt_metadata_deeply_nested_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "receipt.json"
            path.write_text("[" * 1200 + "0" + "]" * 1200)
            with patch.object(agent, "Path", return_value=path):
                self.assertIn(agent.acme_receipt_status()["status"], {"NOT_AVAILABLE", "INVALID"})

    def test_acme_receipt_metadata_invalid_status_type(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "receipt.json"
            path.write_text(json.dumps({"status": ["PASS"]}))
            with patch.object(agent, "Path", return_value=path):
                self.assertEqual(agent.acme_receipt_status()["status"], "INVALID")

    def test_acme_receipt_metadata_invalid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "receipt.json"
            path.write_text("{broken")
            with patch.object(agent, "Path", return_value=path):
                self.assertEqual(agent.acme_receipt_status()["status"], "NOT_AVAILABLE")

    def test_untrusted_author(self):
        self.assertIsNone(agent.parse(comment(login="attacker"), NOW))

    def test_wrong_issue(self):
        self.assertIsNone(agent.parse(comment(url="https://github.com/alimtalbi-ata/aiops/issues/999#issuecomment-12"), NOW))

    def test_expired(self):
        self.assertIsNone(agent.parse(comment(), NOW + dt.timedelta(hours=2)))

    def test_too_long_ttl(self):
        self.assertIsNone(agent.parse(comment(body=VALID.replace("17:00:00", "19:00:00")), NOW))

    def test_no_arbitrary_commands(self):
        self.assertIsNone(agent.parse(comment(body=VALID.replace("status", "shell")), NOW))

    def test_no_multiline_injection(self):
        self.assertIsNone(agent.parse(comment(body=VALID + "\\nrm -rf /"), NOW))

    def test_paid_api_action_rejected(self):
        self.assertIsNone(agent.parse(comment(body=VALID.replace("status", "openai_summary")), NOW))

if __name__ == "__main__":
    unittest.main()
