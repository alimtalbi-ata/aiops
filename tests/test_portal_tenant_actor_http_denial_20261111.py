"""HTTP-level fail-closed proof for the existing portal bootstrap.

A successful shared viewer bearer MUST NOT authorize Core/Twin reads.
This test uses no production secrets, no external services, and no tenant data.
"""
import importlib
from pathlib import Path

from fastapi.testclient import TestClient


def test_authenticated_shared_viewer_cannot_read_tenant_bootstrap(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "app"))
    portal = importlib.import_module("portal.main")
    calls = []

    def accepted_shared_viewer(_authorization):
        calls.append("viewer-auth")

    def forbidden_upstream(*_args, **_kwargs):
        raise AssertionError("Core/Twin upstream must not be contacted")

    monkeypatch.setattr(portal, "_require_portal_read_auth", accepted_shared_viewer)
    monkeypatch.setattr(portal, "get_json", forbidden_upstream)
    monkeypatch.setattr(portal, "read_portal_snapshot", forbidden_upstream)

    client = TestClient(portal.app, raise_server_exceptions=False)
    response = client.get(
        "/api/portal/bootstrap",
        headers={"Authorization": "Bearer synthetic-viewer-only"},
    )
    assert calls == ["viewer-auth"]
    assert response.status_code == 503
    body = response.json()
    assert body["state"] == "UNKNOWN"
    assert body["reason"] == "TENANT_ACL_NOT_QUALIFIED"
    assert body["source"] == "CORE_TWIN_READ_MODELS_NOT_TENANT_AUTHORIZED"
    assert "items" not in body
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
