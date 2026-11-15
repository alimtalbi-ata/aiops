"""Server-side authorization boundary for future Portal/Core read integrations.

Not mounted as an HTTP route. The production Portal remains fail-closed until
trusted identity and Core tenant ownership resolvers are actually configured.
The caller must supply server-derived identity and resolvers, never browser
headers, request JSON, shared tokens or unverified claims.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional


@dataclass(frozen=True)
class ReadScope:
    subject_id: str
    tenant_id: str
    run_id: str


@dataclass(frozen=True)
class ReadGrant:
    subject_id: str
    tenant_id: str
    run_id: str
    expires_at: datetime
    evidence_id: str


class UnqualifiedReadPermission(Exception):
    pass


def read_authorized_run(
    scope: ReadScope,
    *,
    resolve_grant: Callable[[ReadScope], Optional[ReadGrant]],
    resolve_run_tenant: Callable[[str], Optional[str]],
    read_run: Callable[[str, str], dict],
    now: datetime,
) -> dict:
    """Return only synthetic, exact-Run data after both server ACL checks.

    Never use with a live Core reader without a separate reviewed tenant-scoped
    Core contract. This boundary intentionally permits only synthetic fixtures.
    """
    denied = UnqualifiedReadPermission("TENANT_ACL_NOT_QUALIFIED")
    if not isinstance(scope, ReadScope) or not isinstance(now, datetime):
        raise denied
    if now.tzinfo is None or now.utcoffset() is None:
        raise denied
    if any(not isinstance(x, str) or not x.strip()
           for x in (scope.subject_id, scope.tenant_id, scope.run_id)):
        raise denied
    try:
        grant = resolve_grant(scope)
    except Exception:
        raise denied from None
    if not isinstance(grant, ReadGrant):
        raise denied
    if not isinstance(grant.expires_at, datetime) or grant.expires_at.tzinfo is None:
        raise denied
    if grant.expires_at.utcoffset() is None or grant.expires_at <= now.astimezone(grant.expires_at.tzinfo):
        raise denied
    if (grant.subject_id, grant.tenant_id, grant.run_id) != (
            scope.subject_id, scope.tenant_id, scope.run_id):
        raise denied
    if not isinstance(grant.evidence_id, str) or not grant.evidence_id.strip():
        raise denied
    try:
        owner = resolve_run_tenant(scope.run_id)
    except Exception:
        raise denied from None
    if owner != scope.tenant_id:
        raise denied
    try:
        raw = read_run(scope.tenant_id, scope.run_id)
    except Exception:
        raise denied from None
    if not isinstance(raw, dict) or set(raw) != {
            "run_id", "tenant_id", "state", "live_remediation_authorized"}:
        raise denied
    if (raw["run_id"] != scope.run_id or raw["tenant_id"] != scope.tenant_id
            or raw["state"] != "SYNTHETIC_SIMULATION_ONLY"
            or raw["live_remediation_authorized"] is not False):
        raise denied
    return dict(raw)
