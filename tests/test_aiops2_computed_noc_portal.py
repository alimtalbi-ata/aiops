"""Portal read-only computed NOC route regression."""
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.aiops2_computed_noc_demo import router
from fastapi import FastAPI

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_html_route_renders_computed_synthetic_path():
    response = client.get("/demo/aiops2-computed-noc")
    assert response.status_code == 200
    assert "SIMULATION" in response.text
    assert "san-01 → storage → payments" in response.text
    assert "DENY_LIVE" in response.text
    assert response.headers["cache-control"] == "no-store"


def test_json_route_has_no_live_authorization():
    response = client.get("/demo/api/aiops2-computed-noc")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "SIMULATION"
    assert body["runtime_attested"] is False
    assert body["live_remediation_authorized"] is False
    assert body["decisions"][0]["event_count"] == 2
    assert body["decisions"][0]["impact_state"] == "SOURCED_SYNTHETIC_PATH"


def test_no_write_methods():
    for method in ("post", "put", "patch", "delete"):
        response = getattr(client, method)("/demo/aiops2-computed-noc")
        assert response.status_code == 405
