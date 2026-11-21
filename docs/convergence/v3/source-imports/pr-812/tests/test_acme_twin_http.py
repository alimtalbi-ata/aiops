"""Isolated ASGI integration: real router, local fixture, no active sources."""
import copy
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_impact_read_model import build_acme_impact_read_model, router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


ROUTES = ("acme-impact", "acme-lifecycle", "acme-incident-cockpit", "acme-analyst-critic-review")


def test_all_consumers_share_same_story_and_unknown_freshness(client):
    views = []
    for route in ROUTES:
        response = client.get("/api/demo/" + route)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["runtime_attested"] is False if route != "acme-analyst-critic-review" else response.json()["runtime_citations_verified"] == 0
        views.append(response.json()["twin_consumer"])
    assert all(v == views[0] for v in views)
    assert views[0]["structural_impact"]["target_path_count"] == 2
    assert views[0]["freshness"]["status"] == "UNKNOWN"
    assert client.post("/api/demo/acme-impact").status_code == 405


@pytest.mark.parametrize("route", ROUTES[1:])
@pytest.mark.parametrize("key,value", [("tenant_id", "acme"), ("freshness", "FRESH"), ("source_sha256", "0" * 64)])
def test_downstream_rejects_mixed_snapshot_or_authority(client, route, key, value):
    model = copy.deepcopy(build_acme_impact_read_model())
    model["twin_evidence"][key] = value
    with patch("portal.acme_impact_read_model.build_acme_impact_read_model", return_value=model):
        assert client.get("/api/demo/" + route).status_code == 503


def test_legacy_story_fields_remain(client):
    model = client.get("/api/demo/acme-impact").json()
    assert model["schema"] == "aiops.synthetic-impact-read-model.v1"
    assert model["entrypoint"] == "/"
    assert model["ticket_id"] is None
    assert model["event_timestamp_utc"] is None
    assert model["impact_path"] == model["twin_evidence"]["impact"]["impact_path"]
    assert len(model["checkpoint_evidence"]) == 9
    assert model["decision_preview"]["policy"]["decision"] == "DENY_LIVE_ACTION"
