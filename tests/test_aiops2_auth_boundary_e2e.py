"""E2E security boundary: malformed requests and credential collisions never reach Core."""
import socket

from fastapi.testclient import TestClient
from portal.main import app


def test_e2e_token_collision_and_untrusted_body_fail_closed(monkeypatch):
    viewer = "v" * 40
    operator = "o" * 40
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN", viewer)
    monkeypatch.setenv("AIOPS_PORTAL_OPERATOR_TOKEN", viewer)
    monkeypatch.setenv("AIOPS_INTERNAL_TOKEN", "i" * 40)

    def deny_network(*args, **kwargs):
        raise AssertionError("unexpected network access")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket.socket, "connect_ex", deny_network)
    client = TestClient(app)

    # Colliding operator/viewer credentials must not enable any DEMO command.
    for supplied in ("Bearer " + viewer, "Bearer " + operator, "Bearer " + "x" * 40):
        response = client.post(
            "/api/demo",
            headers={"Authorization": supplied, "Content-Type": "application/json"},
            content=b"{not json",
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "portal_operator_not_configured"
        assert response.headers["cache-control"] == "no-store"

    monkeypatch.setenv("AIOPS_PORTAL_OPERATOR_TOKEN", operator)
    for supplied in (
        "Bearer " + viewer, "Bearer " + "x" * 40,
        "Basic " + operator, "Bearer " + operator + " extra",
    ):
        response = client.post(
            "/api/demo",
            headers={"Authorization": supplied, "Content-Type": "application/json"},
            content=b"{not json",
        )
        assert response.status_code == 401

    # Correct operator credential is authentication only, never tenant/Run authority.
    response = client.post(
        "/api/demo",
        headers={"Authorization": "Bearer " + operator, "Content-Type": "application/json"},
        content=b"{not json",
    )
    assert response.status_code == 503
    assert response.json()["reason"] == "TENANT_ACL_NOT_QUALIFIED"
    assert response.json()["live_remediation_authorized"] is False
