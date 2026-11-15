"""Regression for the integrated computed NOC link and read-only route.

No network, authenticated runtime, or deployment required.
"""
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.main import app


def test_portal_home_links_to_computed_simulation():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/demo/aiops2-computed-noc"' in response.text
    assert "NOC calculé (SIMULATION)" in response.text


def test_integrated_computed_noc_routes_are_read_only():
    client = TestClient(app)
    html = client.get("/demo/aiops2-computed-noc")
    assert html.status_code == 200
    assert "DENY_LIVE" in html.text
    assert "SIMULATION" in html.text
    data = client.get("/demo/api/aiops2-computed-noc")
    assert data.status_code == 200
    assert data.json()["runtime_attested"] is False
    assert data.json()["live_remediation_authorized"] is False
    for path in ("/demo/aiops2-computed-noc", "/demo/api/aiops2-computed-noc"):
        for method in ("post", "put", "patch", "delete"):
            assert getattr(client, method)(path).status_code == 405
