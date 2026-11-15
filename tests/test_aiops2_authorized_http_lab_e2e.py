"""Laboratory HTTP contract: authorized synthetic reads, tenant isolation, no LIVE.

This app is test-only. It does not mount a production Portal route and does
not imply that shared bearer tokens constitute an actor identity.
"""
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_server_authorization import AccessRequest, ServerGrant, authorize

NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)


def test_http_lab_actor_tenant_run_authorization_and_no_upstream_on_denial():
    app = FastAPI()
    upstream_calls = []
    trusted_subject = "actor-1"  # Resolved by the lab server, never a browser claim.
    trusted_tenant = "tenant-a"
    owner_by_run = {"run-a": "tenant-a", "run-b": "tenant-b"}

    def grant(request):
        if request.subject_id != trusted_subject:
            return None
        return ServerGrant(request.subject_id, trusted_tenant, request.run_id,
                           "core.run", "read", NOW + timedelta(minutes=5),
                           "lab-policy-1", "lab-evidence-1")

    def run_owner(run_id):
        return owner_by_run.get(run_id)

    @app.get("/lab/runs/{run_id}")
    def read_run(run_id: str, request: Request):
        # Browser-supplied actor/tenant headers and query strings are ignored.
        access = AccessRequest(trusted_subject, trusted_tenant, run_id,
                               "core.run", "read")
        decision = authorize(access, resolve_grant=grant,
                             resolve_run_tenant=run_owner, now=NOW)
        headers = {"Cache-Control": "no-store"}
        if not decision.allowed:
            return JSONResponse({"state": "UNKNOWN",
                                 "reason": "AUTHORIZATION_NOT_QUALIFIED",
                                 "live_remediation_authorized": False},
                                status_code=403, headers=headers)
        upstream_calls.append((trusted_tenant, run_id))
        return JSONResponse({"state": "SYNTHETIC_SIMULATION_ONLY",
                             "run_id": run_id, "tenant_id": trusted_tenant,
                             "live_remediation_authorized": False},
                            headers=headers)

    client = TestClient(app)
    ok = client.get("/lab/runs/run-a",
                    headers={"X-Actor-ID": "other", "X-Tenant-ID": "tenant-b"})
    assert ok.status_code == 200
    assert ok.json()["run_id"] == "run-a"
    assert ok.json()["tenant_id"] == "tenant-a"
    assert ok.json()["live_remediation_authorized"] is False
    assert ok.headers["cache-control"] == "no-store"
    assert upstream_calls == [("tenant-a", "run-a")]

    for run_id in ("run-b", "missing"):
        denied = client.get(
            f"/lab/runs/{run_id}?tenant_id=tenant-b&actor_id=admin",
            headers={"X-Actor-ID": "admin", "X-Tenant-ID": "tenant-b",
                     "X-Role": "operator"},
        )
        assert denied.status_code == 403
        assert denied.json()["state"] == "UNKNOWN"
        assert denied.json()["live_remediation_authorized"] is False
        assert "tenant-b" not in denied.text
        assert run_id not in denied.text
        assert denied.headers["cache-control"] == "no-store"
    assert upstream_calls == [("tenant-a", "run-a")]
