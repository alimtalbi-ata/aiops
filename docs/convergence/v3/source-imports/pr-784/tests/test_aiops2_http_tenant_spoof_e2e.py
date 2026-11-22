"""Offline HTTP E2E: browser-provided actor/tenant/Run claims grant no access."""
import socket
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.main import app


def test_browser_claims_cannot_upgrade_shared_credentials(monkeypatch):
    viewer, operator, internal = "v" * 40, "o" * 40, "i" * 40
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN", viewer)
    monkeypatch.setenv("AIOPS_PORTAL_OPERATOR_TOKEN", operator)
    monkeypatch.setenv("AIOPS_INTERNAL_TOKEN", internal)
    network_calls = []

    def deny_network(*args, **kwargs):
        network_calls.append(args)
        raise AssertionError("unexpected network access")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket.socket, "connect_ex", deny_network)
    client = TestClient(app)
    spoofed = {
        "X-Actor-ID": "admin", "X-Tenant-ID": "tenant-other",
        "X-Run-ID": "RUN-OTHER", "X-Role": "operator",
    }
    for path in ("/api/portal/bootstrap", "/api/portal/components"):
        response = client.get(
            path + "?actor_id=admin&tenant_id=tenant-other&run_id=RUN-OTHER",
            headers={**spoofed, "Authorization": "Bearer " + viewer},
        )
        assert response.status_code == 503
        assert response.json()["reason"] == "TENANT_ACL_NOT_QUALIFIED"
        assert response.headers["cache-control"] == "no-store"
        assert "RUN-OTHER" not in response.text
        assert "tenant-other" not in response.text

    for path, bearer in (("/api/copilot", viewer), ("/api/demo", operator)):
        response = client.post(
            path + "?tenant_id=tenant-other&run_id=RUN-OTHER",
            headers={**spoofed, "Authorization": "Bearer " + bearer,
                     "Content-Type": "application/json"},
            json={"actor_id": "admin", "tenant_id": "tenant-other",
                  "run_id": "RUN-OTHER", "role": "operator",
                  "execute_live": True},
        )
        assert response.status_code == 503
        assert response.json()["reason"] == "TENANT_ACL_NOT_QUALIFIED"
        assert response.headers["cache-control"] == "no-store"
        assert "RUN-OTHER" not in response.text
        assert "tenant-other" not in response.text
        if path == "/api/demo":
            assert response.json()["live_remediation_authorized"] is False
    assert network_calls == []
