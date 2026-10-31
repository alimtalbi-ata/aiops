import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "i" * 64)
from fastapi.testclient import TestClient
from portal import glpi_run_context as module
from portal.main import app


RUN_ID = "RUN-ABCDEF123456"
OPERATOR = "p" * 64


class FakeGLPI:
    configured = True

    def get_ticket(self, ticket_id):
        return {"name": "[AIOps2][DEMO] Payment issue " + RUN_ID,
                "content": "Run: " + RUN_ID}

    def add_private_followup(self, ticket_id, marker, content):
        assert marker in content
        return {"id": 987, "idempotent": False, "is_private": True}


class GLPIRunContextTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AIOPS_PORTAL_OPERATOR_TOKEN": OPERATOR,
            "AIOPS_PORTAL_READ_TOKEN": "q" * 64,
            "AIOPS_INTERNAL_TOKEN": "i" * 64,
        })
        self.env.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.env.stop()

    def headers(self):
        return {"Authorization": "Bearer " + OPERATOR}

    def test_ticket_links_only_to_verified_acme_demo_run(self):
        run = {"run": {"run_id": RUN_ID, "mode": "DEMO",
                       "scenario_id": "SCN-GOLDEN-PAYMENT-P1"}}
        seen = {}
        def copilot(base, path, payload, **kwargs):
            seen.update(payload)
            return {"answer": {"answer": "grounded"}, "sources": ["core:/api/runs/" + RUN_ID]}
        with patch.object(module, "GLPIClient", FakeGLPI), \
             patch.object(module, "get_json", return_value=run), \
             patch.object(module, "post_json", side_effect=copilot):
            response = self.client.post("/api/copilot/glpi-ticket/1", headers=self.headers(),
                                         json={"question": "Analyse ce ticket."})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(seen["run_id"], RUN_ID)
        self.assertEqual(seen["ticket_context"]["id"], "1")
        self.assertEqual(response.json()["run_link"]["status"], "LINKED")
        self.assertIn("glpi:/Ticket/1", response.json()["sources"])

    def test_ambiguous_run_reference_is_refused_before_core_or_model(self):
        class AmbiguousGLPI:
            configured = True
            def get_ticket(self, ticket_id):
                return {"name": "RUN-AAAAAA and RUN-BBBBBB", "content": ""}
        core = Mock(side_effect=AssertionError("ambiguous references must not query Core"))
        model = Mock(side_effect=AssertionError("ambiguous references must not call NIM"))
        with patch.object(module, "GLPIClient", AmbiguousGLPI), \
             patch.object(module, "get_json", core), patch.object(module, "post_json", model):
            response = self.client.post("/api/copilot/glpi-ticket/2", headers=self.headers(),
                                         json={"question": "Analyse ce ticket."})
        self.assertEqual(response.status_code, 409)
        core.assert_not_called()
        model.assert_not_called()

    def test_hitl_proposal_requires_clean_analyst_critic_and_writes_private_note(self):
        evidence = ["EVD-1234567890"]
        action = {
            "action_id": "CI-COLLECT-READONLY", "intent": "Collect read-only diagnostics.",
            "risk_tier": "LOW", "evidence_ids": evidence, "target_ci_id": "ACME-SYNTHETIC",
            "advisory_only": True, "preconditions": ["Confirm scope"],
            "rollback_plan": "No side effects.", "expected_effect": "New read-only observations",
            "verification_steps": ["Check provenance"], "requires_human_approval": True,
        }
        analysis = {"analysis_id": "ANL-1234567890", "status": "VALID",
                    "evidence_ids": evidence, "output": {"recommended_actions": [action]}}
        critique = {"critique_id": "CRT-1234567890", "analysis_id": analysis["analysis_id"],
                    "validated": True, "evidence_ids": evidence,
                    "output": {"issues": [], "unsafe_actions": []}}
        def read_core(base, path, **kwargs):
            if path == "/api/runs/" + RUN_ID:
                return {"run": {"run_id": RUN_ID, "mode": "DEMO",
                                "scenario_id": "SCN-GOLDEN-PAYMENT-P1"}}
            if path == "/api/runs/" + RUN_ID + "/ai-ledger":
                return {"analyses": [analysis], "critiques": [critique]}
            raise AssertionError(path)
        calls = []
        def post(base, path, payload, **kwargs):
            calls.append((path, payload))
            if path == "/api/copilot/query":
                return {"answer": {"answer": "grounded"}, "sources": ["core:/api/runs/" + RUN_ID]}
            if path == "/api/runs/" + RUN_ID + "/proposals":
                return {"proposal_id": "ACT-1234567890", "revision": 1,
                        "proposal_hash": "a" * 64, "status": "PROPOSED",
                        "execution_allowed": False, "idempotent": False}
            raise AssertionError(path)
        with patch.object(module, "GLPIClient", FakeGLPI), \
             patch.object(module, "get_json", side_effect=read_core), \
             patch.object(module, "post_json", side_effect=post):
            response = self.client.post("/api/hitl/glpi-ticket/1/proposal",
                headers=self.headers(),
                json={"source_action_id": "CI-COLLECT-READONLY",
                      "question": "Prépare une proposition prudente."})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["approval_required"])
        self.assertFalse(body["execution_allowed"])
        self.assertEqual(body["hitl_proposal"]["status"], "PROPOSED")
        self.assertTrue(body["glpi_followup"]["is_private"])
        self.assertEqual(body["glpi_followup"]["id"], 987)
        proposal_call = next(call for call in calls if call[0].endswith("/proposals"))
        self.assertEqual(proposal_call[1]["action_type"], "COLLECT_DIAGNOSTICS")
        self.assertEqual(proposal_call[1]["evidence_ids"], evidence)

    def test_unmapped_action_is_rejected_without_writes(self):
        post = Mock(side_effect=AssertionError("unmapped action must not write"))
        with patch.object(module, "GLPIClient", FakeGLPI), patch.object(module, "post_json", post):
            response = self.client.post("/api/hitl/glpi-ticket/1/proposal",
                headers=self.headers(), json={"source_action_id": "RESTART-SERVICE"})
        self.assertEqual(response.status_code, 422)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
