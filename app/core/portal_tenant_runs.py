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
