"""Offline ASGI integration of synthetic signals."""
import copy
import sys
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_impact_read_model import router, build_acme_impact_read_model


def test_signals_shared_and_fail_closed():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    a = client.get("/api/demo/acme-impact")
    b = client.get("/api/demo/acme-incident-cockpit")
    assert a.status_code == b.status_code == 200
    assert a.json()["signal_context"] == b.json()["signal_context"]
    assert a.json()["signal_context"]["duplicate_count"] == 1
    assert b.json()["signal_context"]["runtime_attested"] is False
    bad = copy.deepcopy(build_acme_impact_read_model())
    bad["signal_context"]["runtime_attested"] = True
    with patch("portal.acme_impact_read_model.build_acme_impact_read_model", return_value=bad):
        assert client.get("/api/demo/acme-incident-cockpit").status_code == 503
