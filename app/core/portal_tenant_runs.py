"""Tenant-scoped Runs read query for a future authenticated Core adapter.

The caller MUST derive actor_id from verified server-side identity. Neither a
browser-supplied actor ID nor a tenant ID is authorization. This module does not
expose an endpoint and cannot change the legacy global read endpoints.
"""
from __future__ import annotations

import re

ACTOR_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@-]{0,199}\Z")
MAX_RUNS = 100

RUNS_FOR_ACTOR_SQL = """
select r.run_id, r.incident_id, r.mode, r.scenario_id, r.status,
       r.version, r.overall_confidence, r.created_at, r.started_at,
       r.completed_at
from aiops.runs as r
join aiops.portal_run_tenant_bindings as b on b.run_id = r.run_id
join aiops.portal_actor_tenant_grants as g on g.tenant_id = b.tenant_id
where g.actor_id = %s and g.revoked_at is null
order by r.created_at desc, r.run_id desc
limit %s
"""

RUN_FIELDS = (
    "run_id", "incident_id", "mode", "scenario_id", "status",
    "version", "overall_confidence", "created_at", "started_at",
    "completed_at",
)


def read_runs_for_verified_actor(cursor, *, actor_id: str, limit: int = MAX_RUNS) -> dict:
    """Use only after a trusted identity provider has verified actor_id.

    No tenant fallback, no global read, no unbound historical Runs. Revocation
    is checked by SQL on each read. Cursor is supplied by the calling Core DB
    transaction; this function never accepts authorization headers or tokens.
    """
    if not isinstance(actor_id, str) or not ACTOR_ID.fullmatch(actor_id):
        raise ValueError("verified actor identity required")
    if type(limit) is not int or not 1 <= limit <= MAX_RUNS:
        raise ValueError("invalid bounded Runs limit")
    rows = cursor.execute(RUNS_FOR_ACTOR_SQL, (actor_id, limit)).fetchall()
    return {"items": [dict(zip(RUN_FIELDS, row)) for row in rows]}


def read_runs_for_bearer(connect, *, bearer_token: str, limit: int = MAX_RUNS) -> dict:
    """Resolve a verified OIDC bearer through durable JTI revocation, then read.

    The caller supplies only a server-owned PostgreSQL connection factory and
    the bearer token. Actor and tenant identifiers are never caller inputs.
    The tenant-scoped SQL remains the sole source of row authorization. There
    is intentionally no global fallback and no upstream/GLPI call in this path.
    """
    from shared.oidc_jti_store import make_oidc_jti_store
    from shared.verified_principal import principal_from_bearer

    is_revoked, _, _ = make_oidc_jti_store(connect)
    principal = principal_from_bearer(bearer_token, is_revoked=is_revoked)

    connection = connect()
    try:
        with connection:
            with connection.cursor() as cursor:
                return read_runs_for_verified_actor(
                    cursor, actor_id=principal.actor_id, limit=limit
                )
    finally:
        connection.close()


# Exact-Run read is authorized by Core's own tenant bindings and actor grants.
# No Portal-supplied tenant is used; a missing row reveals no Run metadata.
EXACT_RUN_FOR_ACTOR_SQL = """
select r.run_id, r.incident_id, r.mode, r.scenario_id, r.status,
       r.version, r.overall_confidence, r.created_at, r.started_at,
       r.completed_at
from aiops.runs as r
join aiops.portal_run_tenant_bindings as b on b.run_id = r.run_id
join aiops.portal_actor_tenant_grants as g on g.tenant_id = b.tenant_id
where r.run_id = %s and g.actor_id = %s and g.revoked_at is null
limit 1
"""


def read_exact_run_for_verified_actor(cursor, *, actor_id: str, run_id: str) -> dict | None:
    """Core-owned tenant-scoped read, requiring independently verified actor.

    The caller MUST obtain actor_id from principal_from_bearer with durable JTI
    revocation, not from Portal headers or request JSON. Not mounted as a route.
    """
    if not isinstance(actor_id, str) or not ACTOR_ID.fullmatch(actor_id):
        raise ValueError("verified actor identity required")
    if (not isinstance(run_id, str) or not run_id.startswith("RUN-")
            or not ACTOR_ID.fullmatch(run_id)):
        raise ValueError("invalid exact Run scope")
    row = cursor.execute(EXACT_RUN_FOR_ACTOR_SQL, (run_id, actor_id)).fetchone()
    return dict(zip(RUN_FIELDS, row)) if row is not None else None


def read_exact_run_for_bearer(connect, *, bearer_token: str, run_id: str) -> dict | None:
    """Independently verify OIDC and durable JTI revocation before exact-Run SQL.

    No HTTP route is mounted. The caller must not treat an internal shared
    bearer as an OIDC token. Unauthorized and missing Runs both return None.
    """
    from shared.oidc_jti_store import make_oidc_jti_store
    from shared.verified_principal import principal_from_bearer

    if (not isinstance(run_id, str) or not run_id.startswith("RUN-")
            or not ACTOR_ID.fullmatch(run_id)):
        raise ValueError("invalid exact Run scope")
    is_revoked, _, _ = make_oidc_jti_store(connect)
    principal = principal_from_bearer(bearer_token, is_revoked=is_revoked)

    connection = connect()
    try:
        with connection:
            with connection.cursor() as cursor:
                return read_exact_run_for_verified_actor(
                    cursor, actor_id=principal.actor_id, run_id=run_id
                )
    finally:
        connection.close()
