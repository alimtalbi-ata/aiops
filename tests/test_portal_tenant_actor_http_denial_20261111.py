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


def test_rejected_viewer_cannot_reach_upstream_or_disclose_rows(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "app"))
    portal = importlib.import_module("portal.main")
    from fastapi import HTTPException

    def denied_viewer(_authorization):
        raise HTTPException(status_code=403, detail="unauthorized")

    def forbidden_upstream(*_args, **_kwargs):
        raise AssertionError("unauthorized request reached Core/Twin")

    monkeypatch.setattr(portal, "_require_portal_read_auth", denied_viewer)
    monkeypatch.setattr(portal, "get_json", forbidden_upstream)
    monkeypatch.setattr(portal, "read_portal_snapshot", forbidden_upstream)
    client = TestClient(portal.app, raise_server_exceptions=False)
    response = client.get(
        "/api/portal/bootstrap",
        headers={"Authorization": "Bearer synthetic-rejected"},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "unauthorized"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_missing_bearer_is_denied_before_any_upstream_access(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "app"))
    portal = importlib.import_module("portal.main")
    from fastapi import HTTPException

    def require_bearer(authorization):
        assert authorization is None
        raise HTTPException(status_code=401, detail="unauthorized")

    def forbidden_upstream(*_args, **_kwargs):
        raise AssertionError("missing bearer reached Core/Twin")

    monkeypatch.setattr(portal, "_require_portal_read_auth", require_bearer)
    monkeypatch.setattr(portal, "get_json", forbidden_upstream)
    monkeypatch.setattr(portal, "read_portal_snapshot", forbidden_upstream)
    response = TestClient(portal.app, raise_server_exceptions=False).get(
        "/api/portal/bootstrap"
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_real_viewer_auth_accepts_token_but_never_qualifies_tenant(monkeypatch):
    """Exercise the real constant-time bearer gate, not an auth stub."""
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "app"))
    portal = importlib.import_module("portal.main")
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN", "synthetic-test-secret")

    def forbidden_upstream(*_args, **_kwargs):
        raise AssertionError("shared bearer must not enable Core/Twin reads")

    monkeypatch.setattr(portal, "get_json", forbidden_upstream)
    monkeypatch.setattr(portal, "read_portal_snapshot", forbidden_upstream)
    client = TestClient(portal.app, raise_server_exceptions=False)
    for bearer, expected_status in (
        ("Bearer synthetic-test-secret", 503),
        ("Bearer incorrect", 401),
        ("Basic synthetic-test-secret", 401),
    ):
        response = client.get(
            "/api/portal/bootstrap", headers={"Authorization": bearer}
        )
        assert response.status_code == expected_status
        assert response.headers["cache-control"] == "no-store"
        if expected_status == 503:
            assert response.json()["reason"] == "TENANT_ACL_NOT_QUALIFIED"
        else:
            assert response.json()["detail"] == "invalid_portal_read_token"


def test_spoofed_actor_tenant_and_proxy_headers_cannot_upgrade_viewer(monkeypatch):
    """Untrusted browser headers must never qualify a shared viewer token."""
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "app"))
    portal = importlib.import_module("portal.main")
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN", "synthetic-test-secret")

    def forbidden_upstream(*_args, **_kwargs):
        raise AssertionError("spoofed identity reached an upstream service")

    monkeypatch.setattr(portal, "get_json", forbidden_upstream)
    monkeypatch.setattr(portal, "post_json", forbidden_upstream)
    monkeypatch.setattr(portal, "read_portal_snapshot", forbidden_upstream)
    client = TestClient(portal.app, raise_server_exceptions=False)
    headers = {
        "Authorization": "Bearer synthetic-test-secret",
        "X-Actor-Id": "admin",
        "X-Tenant-Id": "tenant-b",
        "X-Authenticated-User": "admin",
        "X-Forwarded-User": "admin",
        "X-Remote-User": "admin",
        "X-Forwarded-Email": "admin@example.invalid",
    }
    for method, endpoint in (
        ("get", "/api/portal/bootstrap"),
        ("get", "/api/portal/components"),
        ("post", "/api/copilot"),
    ):
        response = getattr(client, method)(endpoint, headers=headers)
        assert response.status_code == 503, endpoint
        assert response.json()["reason"] == "TENANT_ACL_NOT_QUALIFIED"
        assert "items" not in response.json()
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
