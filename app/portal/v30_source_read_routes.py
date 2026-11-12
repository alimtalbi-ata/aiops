"""Fail-closed V30 candidate read endpoints; no upstream or database access.

The shared NOC bearer is authentication only, not actor/tenant authorization.
No browser value can authorize Prometheus, database inventory or GLPI reads.
These routes must not be advertised as LIVE until the deployed V30 router,
server session, datasource tenancy and network path have been qualified.
"""
from fastapi import APIRouter, Header, HTTPException
from portal.noc_runtime import _require_portal_read_auth, _noc_json_response

router = APIRouter()

def _unqualified_read(authorization, source):
    try:
        _require_portal_read_auth(authorization)
    except HTTPException as exc:
        response = _noc_json_response({"state": "BLOCKED", "data": None,
                                      "reason": "UNAUTHENTICATED" if exc.status_code == 401 else "ACCESS_DENIED"},
                                     status_code=exc.status_code)
        response.headers.update(exc.headers or {})
        return response
    # Shared token is not a server-derived actor+tenant ACL.
    return _noc_json_response({
        "state": "UNKNOWN", "reason": "TENANT_ACL_NOT_QUALIFIED",
        "data": None, "source": source, "source_freshness": "UNKNOWN",
        "mode": "LIVE", "tenant_acl_qualified": False,
    }, status_code=503)

@router.get("/prometheus")
@router.get("/api/portal/prometheus")
def prometheus_read(authorization: str | None = Header(default=None)):
    return _unqualified_read(authorization, "PROMETHEUS_NOT_TENANT_ATTESTED")

@router.get("/databases")
@router.get("/api/portal/databases")
def databases_read(authorization: str | None = Header(default=None)):
    return _unqualified_read(authorization, "DATABASE_INVENTORY_NOT_ATTESTED")

@router.get("/cmdb")
@router.get("/api/portal/cmdb")
def cmdb_read(authorization: str | None = Header(default=None)):
    # GLPI is authoritative only when its tenant/CI mapping is attested.
    # Twin is derived and cannot silently replace GLPI.
    return _unqualified_read(authorization, "GLPI_CMDB_NOT_TENANT_ATTESTED")
