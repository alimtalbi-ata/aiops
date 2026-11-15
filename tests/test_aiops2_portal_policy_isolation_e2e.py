"""Actual Portal HTTP E2E: offline lab grants must never open production routes."""
import socket
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.main import app


def test_portal_remains_closed_despite_client_grant_claims(monkeypatch):
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN", "v" * 40)
    monkeypatch.setenv("AIOPS_PORTAL_OPERATOR_TOKEN", "o" * 40)
    monkeypatch.setenv("AIOPS_INTERNAL_TOKEN", "i" * 40)
    calls = []

    def deny_network(*args, **kwargs):
        calls.append(args)
        raise AssertionError("Portal must not call Core/Twin")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket.socket, "connect_ex", deny_network)
    client = TestClient(app)
    forged = {"X-AIOPS-Subject": "admin", "X-AIOPS-Tenant": "tenant-a",
              "X-AIOPS-Run": "run-a", "X-AIOPS-Policy": "ALLOW",
              "X-AIOPS-Evidence": "lab-evidence-1"}
    for path in ("/api/portal/bootstrap", "/api/portal/components"):
        response = client.get(path, headers={**forged, "Authorization": "Bearer " + "v" * 40})
        assert response.status_code == 503
        assert response.json()["reason"] == "TENANT_ACL_NOT_QUALIFIED"
        assert response.headers["cache-control"] == "no-store"
        assert "lab-evidence-1" not in response.text
    for path, token in (("/api/copilot", "v" * 40), ("/api/demo", "o" * 40)):
        response = client.post(path, headers={**forged, "Authorization": "Bearer " + token},
                               json={"subject_id": "admin", "tenant_id": "tenant-a",
                                     "run_id": "run-a", "decision": "ALLOW",
                                     "evidence_id": "lab-evidence-1"})
        assert response.status_code == 503
        assert response.json()["reason"] == "TENANT_ACL_NOT_QUALIFIED"
        assert response.headers["cache-control"] == "no-store"
        assert "lab-evidence-1" not in response.text
        if path == "/api/demo":
            assert response.json()["live_remediation_authorized"] is False
    assert calls == []
