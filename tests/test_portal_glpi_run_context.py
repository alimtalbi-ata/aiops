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
