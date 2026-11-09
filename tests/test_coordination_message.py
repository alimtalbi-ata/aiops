"""Offline contract tests: no network, no GitHub or Debian mutation."""
import copy
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ops" / "coordination"))
from validate_message import InvalidMessage, validate

def sample():
    return {
        "schema_version": "1.0", "message_id": str(uuid.uuid4()),
        "correlation_id": "FS1250-demo-001", "causation_id": None,
        "work_id": "457/core/fs-contract", "kind": "TASK_REQUEST",
        "producer": "schedule.integration", "target": "codex.core",
        "created_at": "2026-11-09T10:00:00Z", "expires_at": "2026-11-09T11:00:00Z",
        "idempotency_key": "457/core/fs-contract:1:codex.core",
        "revision": 1,
        "source": {"repo": "alimtalbi-ata/aiops", "ref": "a" * 40},
        "depends_on": [], "payload_ref": "https://github.com/alimtalbi-ata/aiops/issues/457",
        "evidence_refs": [], "requires_approval": False
    }

class ContractTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate(sample())["kind"], "TASK_REQUEST")

    def test_unknown_actor_rejected(self):
        m = sample(); m["target"] = "shell.root"
        with self.assertRaises(InvalidMessage): validate(m)

    def test_no_branch_ref(self):
        m = sample(); m["source"]["ref"] = "main"
        with self.assertRaises(InvalidMessage): validate(m)

    def test_naive_timestamp_rejected(self):
        m = sample(); m["created_at"] = "2026-11-09T10:00:00"
        with self.assertRaises(InvalidMessage): validate(m)

    def test_expired_order_rejected(self):
        m = sample(); m["expires_at"] = m["created_at"]
        with self.assertRaises(InvalidMessage): validate(m)

    def test_unapproved_deployment_rejected(self):
        m = sample(); m["kind"] = "DEPLOY_CANDIDATE"
        with self.assertRaises(InvalidMessage): validate(m)

    def test_external_payload_rejected(self):
        m = sample(); m["payload_ref"] = "https://evil.example/run"
        with self.assertRaises(InvalidMessage): validate(m)

    def test_self_dependency_rejected(self):
        m = sample(); m["depends_on"] = [m["work_id"]]
        with self.assertRaises(InvalidMessage): validate(m)

    def test_unknown_fields_rejected(self):
        m = sample(); m["command"] = "rm -rf /"
        with self.assertRaises(InvalidMessage): validate(m)

    def test_duplicate_dependencies_rejected(self):
        m = sample(); m["depends_on"] = ["a", "a"]
        with self.assertRaises(InvalidMessage): validate(m)

if __name__ == "__main__":
    unittest.main()
