"""Offline-only reference authorization policy. Not wired to Portal/Core/Twin.

An authenticated bearer alone never supplies actor, tenant or Run authority.
Only a trusted server resolver may populate the context below.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional


@dataclass(frozen=True)
class AccessRequest:
    subject_id: str
    tenant_id: str
    run_id: str
    resource: str
    action: str


@dataclass(frozen=True)
class ServerGrant:
    subject_id: str
    tenant_id: str
    run_id: str
    resource: str
    action: str
    expires_at: datetime
    policy_version: str
    evidence_id: str


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    policy_version: str = ""
    evidence_id: str = ""
    live_remediation_authorized: bool = False


def authorize(
    request: AccessRequest,
    *,
    resolve_grant: Callable[[AccessRequest], Optional[ServerGrant]],
    resolve_run_tenant: Callable[[str], Optional[str]],
    now: datetime,
) -> Decision:
    """Fail closed on absent, conflicting, expired or untrusted server evidence.

    Both resolvers must be trusted server-side implementations. Never bind either
    resolver to request JSON, client headers or unverified bearer claims.
    """
    denied = Decision(False, "AUTHORIZATION_NOT_QUALIFIED")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        return denied
    if any(not isinstance(v, str) or not v.strip() for v in (
        request.subject_id, request.tenant_id, request.run_id,
        request.resource, request.action
    )):
        return denied
    if request.action not in ("read", "simulate"):
        return denied
    if request.resource not in (
        "core.run", "twin.impact", "copilot.context", "demo.command"
    ):
        return denied
    if request.resource == "demo.command" and request.action != "simulate":
        return denied
    try:
        grant = resolve_grant(request)
        owner_tenant = resolve_run_tenant(request.run_id)
    except Exception:
        return denied
    if not isinstance(grant, ServerGrant) or not owner_tenant:
        return denied
    if (not isinstance(grant.expires_at, datetime) or grant.expires_at.tzinfo is None
            or grant.expires_at.utcoffset() is None):
        return denied
    if grant.expires_at.astimezone(timezone.utc) <= now.astimezone(timezone.utc):
        return denied
    if any(not isinstance(value, str) or not value.strip()
           for value in (grant.policy_version, grant.evidence_id)):
        return denied
    if (
        grant.subject_id, grant.tenant_id, grant.run_id,
        grant.resource, grant.action
    ) != (
        request.subject_id, request.tenant_id, request.run_id,
        request.resource, request.action
    ):
        return denied
    if owner_tenant != request.tenant_id:
        return denied
    return Decision(True, "AUTHORIZED_SYNTHETIC_SERVER_GRANT",
                    grant.policy_version, grant.evidence_id)
