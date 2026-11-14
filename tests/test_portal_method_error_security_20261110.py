"""Read-only portal regression: framework 405 responses retain defensive headers.

No tenant identity, credentials, upstream calls, or live mutations are used.
Run: pytest -q tests/test_portal_method_error_security_20261110.py
"""
import importlib
from pathlib import Path

from fastapi.testclient import TestClient


def test_framework_method_not_allowed_is_not_cacheable_or_frameable(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "app"))
    portal = importlib.import_module("portal.main")
    client = TestClient(portal.app, raise_server_exceptions=False)
    # /health only supports GET; POST must be rejected before any app action.
    response = client.post("/health")
    assert response.status_code == 405
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "no-referrer"
