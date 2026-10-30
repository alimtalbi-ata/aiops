from fastapi.testclient import TestClient

from portal import glpi_run_context as route
from portal.main import app
from portal.glpi_report import merge_report, render_run_report


RUN_ID = "RUN-ABCDEF123456"
DETAIL = {
    "run": {
        "run_id": RUN_ID, "incident_id": "INC-TEST-001",
        "mode": "DEMO", "scenario_id": "SCN-TEST-PAYMENTS",
        "status": "BLOCKED", "overall_confidence": 0.82,
    },
    "events": [{
        "sequence": 1, "stage": "DGX_ANALYST", "event_type": "ANALYST_COMPLETED",
        "status": "PASS", "occurred_at": "2026-10-30T09:00:00Z",
        "evidence_ids": ["EVD-1"],
        "payload": {"analysis": {
            "summary": "Latence paiement observée",
            "facts": ["p95 à 340 ms"], "hypotheses": ["Saturation possible"],
            "uncertainties": ["Corrélation non démontrée"],
            "recommended_actions": [{"action_id": "CI-COLLECT-READONLY"}],
        }},
    }],
}
LEDGER = {
    "analyses": [], "critiques": [{
        "validated": False,
        "output": {"issues": ["Mesure indépendante manquante"],
                   "unsafe_actions": []},
    }],
    "policy_decisions": [],
}


class FakeGLPI:
    configured = True
    tickets = {}
    next_id = 50

    def find_ticket_for_run(self, run_id):
        return next((tid for tid, ticket in self.tickets.items()
                     if run_id in ticket.get("name", "")), None)

    def create_ticket(self, name, content, priority=3, status=1):
        ticket_id = str(self.next_id)
        type(self).next_id += 1
        self.tickets[ticket_id] = {"id": ticket_id, "name": name, "content": content, "status": status}
        return ticket_id

    def get_ticket(self, ticket_id):
        return dict(self.tickets[ticket_id])

    def update_ticket(self, ticket_id, fields):
        self.tickets[ticket_id].update(fields)
        return {"id": ticket_id}


def _client(monkeypatch):
    FakeGLPI.tickets = {}
    FakeGLPI.next_id = 50
    monkeypatch.setenv("AIOPS_INTERNAL_TOKEN", "i" * 64)
    monkeypatch.setattr(route, "GLPIClient", FakeGLPI)
    monkeypatch.setattr(route, "get_json", lambda base, path: (
        DETAIL if path == "/api/runs/" + RUN_ID else LEDGER
    ))
    return TestClient(app)


def test_report_contains_human_readable_facts_hypotheses_and_limits():
    report = render_run_report(DETAIL, LEDGER, sync_stage="DGX_ANALYST")
    assert "Latence paiement observée" in report
    assert "p95 à 340 ms" in report
    assert "Saturation possible" in report
    assert "Corrélation non démontrée" in report
    assert "Mesure indépendante manquante" in report
    assert "RUN-ABCDEF123456" in report


def test_merge_report_preserves_original_and_replaces_owned_section():
    old = '<p>[AIOPS2-AI-REPORT:START]</p>old<p>[AIOPS2-AI-REPORT:END]</p>'
    merged = merge_report("Description initiale" + old, "<p>[AIOPS2-AI-REPORT:START]</p>new<p>[AIOPS2-AI-REPORT:END]</p>")
    assert merged.startswith("Description initiale")
    assert "old" not in merged
    assert merged.count("[AIOPS2-AI-REPORT:START]") == 1
    assert ">new<p>[AIOPS2-AI-REPORT:END]</p>" in merged


def test_internal_sync_creates_and_reads_back_ticket(monkeypatch):
    client = _client(monkeypatch)
    response = client.post(
        f"/api/internal/glpi/runs/{RUN_ID}/sync",
        headers={"Authorization": "Bearer " + "i" * 64},
        json={"stage": "DGX_ANALYST"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SYNCED"
    assert body["operation"] == "CREATED"
    assert body["ticket_id"] == "50"
    assert body["report_verified"] is True
    assert body["glpi_status"] == 2
    assert ticket_status := FakeGLPI.tickets["50"]["status"] == 2
    ticket = FakeGLPI.tickets["50"]
    assert RUN_ID in ticket["name"]
    assert "Faits observés" in ticket["content"]


def test_internal_sync_updates_existing_ticket_without_duplicate_report(monkeypatch):
    client = _client(monkeypatch)
    FakeGLPI.tickets["9"] = {
        "id": "9", "name": "[AIOps2] " + RUN_ID,
        "content": "Description opérateur d'origine"
        '<p>[AIOPS2-AI-REPORT:START]</p>ancienne version<p>[AIOPS2-AI-REPORT:END]</p>',
    }
    response = client.post(
        f"/api/internal/glpi/runs/{RUN_ID}/sync",
        headers={"Authorization": "Bearer " + "i" * 64},
        json={"stage": "FINAL"},
    )
    assert response.status_code == 200
    assert response.json()["operation"] == "UPDATED"
    content = FakeGLPI.tickets["9"]["content"]
    assert content.startswith("Description opérateur d'origine")
    assert "ancienne version" not in content
    assert content.count("[AIOPS2-AI-REPORT:START]") == 1
