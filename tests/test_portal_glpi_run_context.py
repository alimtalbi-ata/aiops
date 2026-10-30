import os

from fastapi.testclient import TestClient

from portal import glpi_run_context as module
from portal.main import app


class FakeGLPI:
    configured = True

    def get_ticket(self, ticket_id):
        return {
            "name": "[AIOps2][DEMO] Payment issue RUN-ABCDEF123456",
            "content": "Run: RUN-ABCDEF123456",
        }


def test_glpi_ticket_fastpath_links_only_verified_run(monkeypatch):
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN", "p" * 64)
    monkeypatch.setattr(module, "GLPIClient", FakeGLPI)
    monkeypatch.setattr(module, "get_json", lambda base, path: {
        "run": {"run_id": "RUN-ABCDEF123456", "mode": "DEMO"}
    })
    seen = {}

    def copilot(base, path, payload):
        seen.update(payload)
        return {"answer": "grounded", "sources": ["core:/api/runs/RUN-ABCDEF123456"]}

    monkeypatch.setattr(module, "post_json", copilot)
    response = TestClient(app).post(
        "/api/copilot/glpi-ticket/1",
        headers={"Authorization": "Bearer " + "p" * 64},
        json={"question": "Analyse le ticket et prépare une proposition HITL."},
    )
    assert response.status_code == 200
    body = response.json()
    assert seen["run_id"] == "RUN-ABCDEF123456"
    assert body["run_link"]["status"] == "LINKED"
    assert body["run_link"]["proposal_created"] is False
    assert "glpi:/Ticket/1" in body["sources"]


def test_glpi_ticket_fastpath_does_not_guess_ambiguous_run(monkeypatch):
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN", "p" * 64)

    class AmbiguousGLPI:
        configured = True

        def get_ticket(self, ticket_id):
            return {"name": "RUN-AAAAAA and RUN-BBBBBB", "content": ""}

    monkeypatch.setattr(module, "GLPIClient", AmbiguousGLPI)
    monkeypatch.setattr(module, "get_json", lambda *args: (_ for _ in ()).throw(
        AssertionError("ambiguous references must not trigger Core lookup")))
    seen = {}
    monkeypatch.setattr(module, "post_json", lambda base, path, payload: (
        seen.update(payload) or {"answer": "unknown", "sources": []}))
    response = TestClient(app).post(
        "/api/copilot/glpi-ticket/2",
        headers={"Authorization": "Bearer " + "p" * 64},
        json={"question": "Analyse ce ticket."},
    )
    assert response.status_code == 200
    assert seen["run_id"] is None
    assert response.json()["run_link"]["status"] == "UNKNOWN"



def test_glpi_hitl_fastpath_creates_only_guarded_proposal(monkeypatch):
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN", "p" * 64)
    monkeypatch.setattr(module, "GLPIClient", FakeGLPI)

    run_id = "RUN-ABCDEF123456"
    analysis_id = "ANL-1234567890"
    critique_id = "CRT-1234567890"
    evidence = ["EVD-1234567890"]
    action = {
        "action_id": "CI-COLLECT-READONLY",
        "intent": "Collect additional read-only diagnostics.",
        "risk_tier": "LOW",
        "evidence_ids": evidence,
        "target_ci_id": "ACME-SYNTHETIC",
        "advisory_only": True,
        "preconditions": ["Confirm scope", "No infrastructure state change"],
        "rollback_plan": "No side effects; none required.",
        "expected_effect": "New read-only observations",
        "verification_steps": ["Check observed time and independent provenance"],
        "requires_human_approval": True,
    }
    analysis = {
        "analysis_id": analysis_id, "status": "VALID",
        "evidence_ids": evidence,
        "output": {"recommended_actions": [action]},
    }
    critique = {
        "critique_id": critique_id, "analysis_id": analysis_id,
        "validated": True, "evidence_ids": evidence,
        "output": {"issues": [], "unsafe_actions": []},
    }

    def read_core(base, path):
        if path == "/api/runs/" + run_id:
            return {"run": {"run_id": run_id, "mode": "DEMO"}}
        if path == "/api/runs/" + run_id + "/ai-ledger":
            return {"analyses": [analysis], "critiques": [critique]}
        raise AssertionError("unexpected Core read: " + path)

    monkeypatch.setattr(module, "get_json", read_core)
    calls = []

    def post(base, path, payload):
        calls.append((path, payload))
        if path == "/api/copilot/query":
            return {"answer": "grounded", "sources": ["core:/api/runs/" + run_id]}
        if path == "/api/runs/" + run_id + "/proposals":
            return {
                "proposal_id": "ACT-1234567890", "revision": 1,
                "proposal_hash": "a" * 64, "status": "PROPOSED",
                "execution_allowed": False, "idempotent": False,
            }
        raise AssertionError("unexpected POST: " + path)

    monkeypatch.setattr(module, "post_json", post)
    response = TestClient(app).post(
        "/api/hitl/glpi-ticket/1/proposal",
        headers={"Authorization": "Bearer " + "p" * 64},
        json={"source_action_id": "CI-COLLECT-READONLY",
              "question": "Analyse les preuves et prépare la proposition."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["run_link"]["run_id"] == run_id
    assert body["run_link"]["proposal_created"] is True
    assert body["hitl_proposal"]["status"] == "PROPOSED"
    assert body["approval_required"] is True
    assert body["execution_allowed"] is False
    proposal_call = next(c for c in calls if c[0].endswith("/proposals"))
    assert proposal_call[1]["action_type"] == "COLLECT_DIAGNOSTICS"
    assert proposal_call[1]["evidence_ids"] == evidence
    assert len([c for c in calls if c[0].endswith("/proposals")]) == 1


def test_glpi_hitl_fastpath_rejects_unmapped_action_without_writes(monkeypatch):
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN", "p" * 64)
    response = TestClient(app).post(
        "/api/hitl/glpi-ticket/1/proposal",
        headers={"Authorization": "Bearer " + "p" * 64},
        json={"source_action_id": "RESTART-SERVICE"},
    )
    assert response.status_code == 422
