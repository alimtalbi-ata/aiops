"""Offline HTTP E2E of the actual dormant Portal read boundary.

Test-only FastAPI mounting. No production routes are registered or enabled.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.authorized_run_boundary import (
    ReadGrant, ReadScope, UnqualifiedReadPermission, read_authorized_run,
)

NOW = datetime(2026, 11, 16, tzinfo=timezone.utc)


def test_real_portal_boundary_over_http_with_server_resolvers():
    app = FastAPI()
    calls = []
    trusted_scope = ReadScope("server-actor", "tenant-a", "RUN-A")
    owners = {"RUN-A": "tenant-a", "RUN-B": "tenant-b"}
    mode = {"grant": "valid"}

    def grant(scope):
        calls.append("grant")
        if mode["grant"] == "absent":
            return None
        resource, action = ("core.run", "read") if mode["grant"] == "valid" else ("demo.command", "simulate")
        return ReadGrant(scope.subject_id, scope.tenant_id, scope.run_id,
                         NOW + timedelta(minutes=5), "server-evidence",
                         resource, action)

    def owner(run_id):
        calls.append("owner")
        return owners.get(run_id)

    def read(tenant_id, run_id):
        calls.append("core")
        return {"run_id": run_id, "tenant_id": tenant_id,
                "state": "SYNTHETIC_SIMULATION_ONLY",
                "live_remediation_authorized": False}

    @app.get("/lab/portal/runs/{run_id}")
    def endpoint(run_id: str, request: Request):
        # This is an offline fixture. Never derive actor or tenant from HTTP.
        scope = ReadScope(trusted_scope.subject_id, trusted_scope.tenant_id, run_id)
        try:
            payload = read_authorized_run(
                scope, resolve_grant=grant, resolve_run_tenant=owner,
                read_run=read, now=NOW)
            return JSONResponse(payload, headers={"Cache-Control": "no-store"})
        except UnqualifiedReadPermission:
            return JSONResponse({"state": "UNKNOWN",
                                 "reason": "TENANT_ACL_NOT_QUALIFIED",
                                 "live_remediation_authorized": False},
                                status_code=403,
                                headers={"Cache-Control": "no-store"})

    client = TestClient(app)
    forged = {"X-Actor-ID": "admin", "X-Tenant-ID": "tenant-b",
              "X-Grant-Resource": "core.run", "X-Grant-Action": "read"}
    ok = client.get("/lab/portal/runs/RUN-A?tenant_id=tenant-b", headers=forged)
    assert ok.status_code == 200
    assert ok.json() == {"run_id": "RUN-A", "tenant_id": "tenant-a",
                         "state": "SYNTHETIC_SIMULATION_ONLY",
                         "live_remediation_authorized": False}
    assert calls == ["grant", "owner", "core"]
    assert ok.headers["cache-control"] == "no-store"

    for run_id in ("RUN-B", "RUN-MISSING"):
        calls.clear()
        denied = client.get("/lab/portal/runs/" + run_id, headers=forged)
        assert denied.status_code == 403
        assert denied.json()["state"] == "UNKNOWN"
        assert "RUN-B" not in denied.text
        assert "tenant-b" not in denied.text
        assert calls == ["grant", "owner"]

    for grant_mode in ("absent", "wrong-action"):
        mode["grant"] = grant_mode
        calls.clear()
        denied = client.get("/lab/portal/runs/RUN-A", headers=forged)
        assert denied.status_code == 403
        assert denied.json()["live_remediation_authorized"] is False
        assert calls == ["grant"]
