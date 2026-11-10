"""Portal regression: a viewer credential is not tenant/actor authorization.

Isolated TestClient only; no Debian, credentials, external calls or live effects.
"""
import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    "method,path,source",
    [
        ("GET", "/api/portal/components", "PORTAL_NAVIGATION_NOT_TENANT_AUTHORIZED"),
        ("GET", "/api/portal/bootstrap", "CORE_TWIN_READ_MODELS_NOT_TENANT_AUTHORIZED"),
        ("POST", "/api/copilot", "COPILOT_NOT_TENANT_AUTHORIZED"),
    ],
)
def test_shared_viewer_never_qualifies_tenant_acl(monkeypatch, method, path, source):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "app"))
    portal = importlib.import_module("portal.main")

    # Simulate successful authentication ONLY, not tenant/actor authorization.
    monkeypatch.setattr(portal, "_require_portal_read_auth", lambda _: None)

    def forbidden(*args, **kwargs):
        raise AssertionError("Unqualified tenant ACL triggered an upstream read")

    monkeypatch.setattr(portal, "get_json", forbidden)
    monkeypatch.setattr(portal, "post_json", forbidden)
    monkeypatch.setattr(portal, "build_navigation", forbidden)
    monkeypatch.setattr(portal, "read_portal_snapshot", forbidden)

    client = TestClient(portal.app, raise_server_exceptions=False)
    response = client.request(method, path, headers={"Authorization": "Bearer synthetic-viewer"})
    assert response.status_code == 503
    body = response.json()
    assert body["state"] == "UNKNOWN"
    assert body["reason"] == "TENANT_ACL_NOT_QUALIFIED"
    assert body["source"] == source
    assert body["source_freshness"] == "UNKNOWN"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
