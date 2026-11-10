"""Regression: portal error responses must not leak cacheable or frameable content.

Source-level candidate test only; does not attest Debian behavior.
"""
import importlib
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def test_portal_error_responses_preserve_security_headers(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "app"))
    portal = importlib.import_module("portal.main")
    client = TestClient(portal.app, raise_server_exceptions=False)
    # A non-existent path exercises FastAPI-generated 404 through middleware.
    response = client.get("/__portal_regression_missing_route__")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "no-referrer"
