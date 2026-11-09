"""State-machine regression tests for the coordination bus."""
import copy
import sys
import unittest
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ops" / "coordination"))
from reduce_events import reduce_messages
from validate_message import InvalidMessage

def event(kind, producer, number, evidence=False):
    return {
        "schema_version": "1.0", "message_id": str(uuid.uuid4()),
        "correlation_id": "FS1250-demo-001", "causation_id": None,
        "work_id": "457/core/fs-contract", "kind": kind,
        "producer": producer, "target": "schedule.integration",
        "created_at": f"2026-11-09T10:{number:02d}:00Z",
        "expires_at": "2026-11-09T12:00:00Z",
        "idempotency_key": f"457/core/fs-contract:{number}:{kind}",
        "revision": number + 1,
        "source": {"repo": "alimtalbi-ata/aiops", "ref": "a" * 40},
        "depends_on": [], "payload_ref": "https://github.com/alimtalbi-ata/aiops/issues/457",
        "evidence_refs": ["https://github.com/alimtalbi-ata/aiops/issues/457"] if evidence else [],
        "requires_approval": kind == "DEPLOY_CANDIDATE"
    }

class ReducerTests(unittest.TestCase):
    def test_request_is_ready_not_running(self):
        self.assertEqual(reduce_messages([event("TASK_REQUEST", "schedule.integration", 0)]), {"457/core/fs-contract": "READY"})

    def test_acceptance_requires_evidence(self):
        with self.assertRaises(InvalidMessage):
            reduce_messages([event("TASK_REQUEST", "schedule.integration", 0), event("TASK_ACCEPTED", "codex.core", 1)])

    def test_acceptance_requires_codex(self):
        with self.assertRaises(InvalidMessage):
            reduce_messages([event("TASK_REQUEST", "schedule.integration", 0), event("TASK_ACCEPTED", "schedule.core", 1, True)])

    def test_verified_handoff(self):
        seq = [event("TASK_REQUEST", "schedule.integration", 0),
               event("TASK_ACCEPTED", "codex.core", 1, True),
               event("ARTIFACT_READY", "codex.core", 2, True),
               event("TEST_RESULT", "github.actions", 3, True)]
        self.assertEqual(reduce_messages(seq)["457/core/fs-contract"], "VERIFIED")

    def test_unverified_test_rejected(self):
        seq = [event("TASK_REQUEST", "schedule.integration", 0),
               event("TASK_ACCEPTED", "codex.core", 1, True),
               event("ARTIFACT_READY", "codex.core", 2, True),
               event("TEST_RESULT", "codex.core", 3, True)]
        with self.assertRaises(InvalidMessage): reduce_messages(seq)

    def test_cannot_skip_to_done(self):
        with self.assertRaises(InvalidMessage):
            reduce_messages([event("TASK_DONE", "codex.core", 0, True)])

    def test_duplicate_event_rejected(self):
        m = event("TASK_REQUEST", "schedule.integration", 0)
        with self.assertRaises(InvalidMessage): reduce_messages([m, m])

    def test_blocked_can_requeue(self):
        seq = [event("TASK_REQUEST", "schedule.integration", 0),
               event("TASK_ACCEPTED", "codex.core", 1, True),
               event("BLOCKED", "codex.core", 2),
               event("TASK_REQUEST", "schedule.integration", 3)]
        self.assertEqual(reduce_messages(seq)["457/core/fs-contract"], "READY")

if __name__ == "__main__":
    unittest.main()
