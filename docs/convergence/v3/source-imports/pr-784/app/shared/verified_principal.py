"""Core-owned principal adapter for verified production OIDC identities.

This adapter derives identity only from the RS256/JWKS verifier. It does not
accept browser actor IDs, tenant IDs, role headers, or simulator assertions.
Replay/revocation is deliberately not claimed here; callers must add the
persistent JTI decision before using this principal for sensitive operations.
"""
from __future__ import annotations

from dataclasses import dataclass

from shared.hitl_identity import IdentityError, verify_oidc_assertion


@dataclass(frozen=True, slots=True)
class VerifiedPrincipal:
    actor_id: str
    issuer: str
    roles: tuple[str, ...]
    groups: tuple[str, ...]
    mapping_version: str
    jti: str
    expires_at: int
    simulated: bool = False


def principal_from_bearer(token: str, *, is_revoked) -> VerifiedPrincipal:
    """Verify OIDC, require a durable revocation check, then derive actor ID.

    is_revoked(issuer=..., jti=...) must be backed by PostgreSQL. Missing,
    failing, or positive revocation checks deny the principal.
    """
    if not callable(is_revoked):
        raise IdentityError("oidc_revocation_store_required")
    claims = verify_oidc_assertion(token)
    actor_id = claims.get("subject_id")
    issuer = claims.get("issuer")
    roles = claims.get("roles")
    groups = claims.get("groups")
    jti = claims.get("jti")
    expires_at = claims.get("expires_at")
    if (
        not isinstance(actor_id, str) or not actor_id.startswith("oidc:")
        or not isinstance(issuer, str) or not issuer.startswith("https://")
        or not isinstance(roles, list) or not roles
        or not isinstance(groups, list) or not groups
        or not isinstance(jti, str) or not jti
        or type(expires_at) is not int
        or claims.get("simulated") is not False
    ):
        raise IdentityError("verified_principal_claims_invalid")
    try:
        revoked = is_revoked(issuer=issuer, jti=jti)
    except Exception as exc:
        raise IdentityError("oidc_revocation_check_failed") from exc
    if revoked is not False:
        raise IdentityError("oidc_assertion_revoked_or_store_unavailable")
    return VerifiedPrincipal(
        actor_id=actor_id,
        issuer=issuer,
        roles=tuple(sorted(set(roles))),
        groups=tuple(sorted(set(groups))),
        mapping_version=str(claims.get("mapping_version") or "unversioned"),
        jti=jti,
        expires_at=expires_at,
        simulated=False,
    )
