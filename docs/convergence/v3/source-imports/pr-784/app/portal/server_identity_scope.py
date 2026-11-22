"""Dormant server identity-to-Run scope boundary for offline integration.

No bearer, cookie, header or client tenant is accepted as identity evidence.
Only a trusted server identity resolver may return an authenticated principal.
Not mounted in production; does not establish a real identity provider.
"""
from dataclasses import dataclass
from typing import Callable, Optional

from portal.authorized_run_boundary import ReadScope, UnqualifiedReadPermission


@dataclass(frozen=True)
class VerifiedPrincipal:
    subject_id: str
    tenant_id: str
    audience: str
    evidence_id: str


EXPECTED_AUDIENCE = "aiops-portal-read"


def resolve_server_read_scope(
    run_id: str,
    *,
    resolve_verified_principal: Callable[[], Optional[VerifiedPrincipal]],
) -> ReadScope:
    """Build scope only from a trusted server-authenticated identity callback.

    The resolver must independently validate issuer/signature, audience, expiry,
    revocation and subject-to-tenant membership. This module cannot do so.
    """
    denied = UnqualifiedReadPermission("TENANT_ACL_NOT_QUALIFIED")
    if not isinstance(run_id, str) or not run_id.strip():
        raise denied
    try:
        principal = resolve_verified_principal()
    except Exception:
        raise denied from None
    if not isinstance(principal, VerifiedPrincipal):
        raise denied
    if any(not isinstance(value, str) or not value.strip() for value in (
        principal.subject_id, principal.tenant_id, principal.evidence_id
    )) or principal.audience != EXPECTED_AUDIENCE:
        raise denied
    return ReadScope(principal.subject_id, principal.tenant_id, run_id)
