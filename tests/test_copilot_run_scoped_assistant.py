import os
import unittest
from unittest.mock import patch

os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "copilot-test-internal-token")
from copilot import main as module


class RunScopedAssistantTests(unittest.TestCase):
    def setUp(self):
        self.run_id = "RUN-ABCDEF123456"
        self.run = {"run_id": self.run_id, "mode": "DEMO",
                    "scenario_id": "SCN-GOLDEN-PAYMENT-P1", "status": "RESOLVED",
                    "incident_id": "INC-1", "version": 29}
        self.ledger = {
            "analyses": [{"output": {"classification": "payment latency"}}],
            "critiques": [{"output": {"validated": True, "issues": [], "unsafe_actions": []}}],
        }
        self.evidence = [{"evidence_id": "E1", "claim": "synthetic latency observation",
                          "confidence": 0.9, "provenance": {"run_id": self.run_id}}]
        self.answer = {
            "answer": {"answer": "La latence est observée.", "claims": [
                {"claim": "latence observée", "supported": True,
                 "supporting_evidence_ids": ["E1"], "contradicting_evidence_ids": []}],
                "follow_up_questions": [], "limitations": []},
            "provider": "NVIDIA_NIM", "model": "nemotron-120b-test",
            "prompt_version": "copilot-answer-v1.0",
            "model_invocation": {"invocation_id": "inv-1", "total_tokens": 150,
                                 "usage_source": "provider_reported"},
        }

    def read(self, base, path, **kwargs):
        if path == "/api/runs/" + self.run_id:
            return {"run": self.run}
        if path == "/api/runs/" + self.run_id + "/ai-ledger":
            return self.ledger
        if path.startswith("/api/evidence?run_id="):
            return {"items": self.evidence}
        if path == "/api/incidents?limit=500":
            return {"items": [{"incident_id": "INC-1", "title": "Payments P1", "severity": "P1"}]}
        raise AssertionError(path)

    def test_real_assistant_call_is_run_scoped_and_audited(self):
        calls = []
        def post(base, path, payload, **kwargs):
            calls.append((base, path, payload))
            if path == "/api/intelligence/answer":
                return self.answer
            if path == "/api/runs/" + self.run_id + "/events":
                return {"run_id": self.run_id, "sequence": 30, "version": 30}
            raise AssertionError(path)
        with patch.object(module, "get_json", side_effect=self.read), patch.object(module, "post_json", side_effect=post):
            result = module.query(module.Q(question="Explique la dégradation.", run_id=self.run_id,
                                           ticket_context={"id": "1", "title": "Synthetic payment"}))
        self.assertEqual(result["provider"], "NVIDIA_NIM")
        self.assertEqual(result["event_sequence"], 30)
        self.assertFalse(result["execution_allowed"])
        self.assertFalse(result["approval_recorded"])
        event = next(c[2] for c in calls if c[1].endswith("/events"))
        self.assertEqual(event["stage"], "LEARN")
        self.assertEqual(event["status"], "PASS")
        self.assertEqual(event["evidence_ids"], ["E1"])
        self.assertEqual(event["decision"], "NO_EXECUTION")
        self.assertIn("question_sha256", event["payload"])
        self.assertNotIn("question", event["payload"])

    def test_live_run_is_refused_before_model_call(self):
        self.run["mode"] = "LIVE"
        with patch.object(module, "get_json", side_effect=self.read), patch.object(module, "post_json") as post:
            with self.assertRaises(Exception):
                module.query(module.Q(question="Explique.", run_id=self.run_id))
        post.assert_not_called()

    def test_missing_critic_ledger_fails_closed(self):
        self.ledger["critiques"] = []
        with patch.object(module, "get_json", side_effect=self.read), patch.object(module, "post_json") as post:
            with self.assertRaises(Exception):
                module.query(module.Q(question="Explique.", run_id=self.run_id))
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
