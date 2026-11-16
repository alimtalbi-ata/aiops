"""Offline contract tests for the Codex-free bridge. Run: python3 -m unittest discover -s ops/github-openai-bridge -p 'test_*.py'"""
import datetime as dt
import importlib.util
import pathlib
import tempfile
import unittest
from unittest.mock import patch

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

    def test_openai_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(agent.openai_summary()["status"], "NOT_CONFIGURED")

if __name__ == "__main__":
    unittest.main()
