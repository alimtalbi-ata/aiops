"""Provider-neutral identity assertions for AIOps2 HITL.

The simulator is deliberately non-production. It can exercise UI and policy
flows but its assertions are rejected by every LIVE authorization check.
No passwords, LDAP binds, SSH keys or sudo commands are handled here.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import hashlib
from functools import lru_cache
from typing import Any

ISSUER = "aiops2-identity-simulator"
AUDIENCE = "aiops2-hitl"
MAX_TTL_SECONDS = 600

# Fictional identities. These are fixtures, not real accounts or AD groups.
SIMULATED_IDENTITIES: dict[str, dict[str, Any]] = {
    "operator.alex": {"display_name": "Alex Operator", "groups": ["GG-AIOPS-Operators"]},
    "senior.sam": {"display_name": "Sam Senior", "groups": ["GG-AIOPS-Senior"]},
    "storage.stella": {"display_name": "Stella Storage", "groups": ["GG-AIOPS-Storage"]},
    "security.sara": {"display_name": "Sara Security", "groups": ["GG-AIOPS-Security"]},
    "incident.ian": {"display_name": "Ian Incident Commander", "groups": ["GG-AIOPS-IncidentCommand"]},
    "platform.pat": {"display_name": "Pat Platform Admin", "groups": ["GG-AIOPS-Admins"]},
}
GROUP_ROLE_MAP = {
    "GG-AIOPS-Operators": ("operator",),
    "GG-AIOPS-Senior": ("senior_operator",),
    "GG-AIOPS-Storage": ("storage_admin",),
    "GG-AIOPS-Security": ("security_admin",),
    "GG-AIOPS-IncidentCommand": ("incident_commander",),
    "GG-AIOPS-Admins": ("platform_admin",),
}


class IdentityError(ValueError):
    """Identity is absent, invalid, expired, simulated or not authorized."""


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def simulator_enabled() -> bool:
    return (
        os.getenv("AIOPS_HITL_IDENTITY_MODE", "").upper() == "SIMULATOR"
        and os.getenv("AIOPS_HITL_SIMULATOR_ENABLED", "").lower() == "true"
    )


def simulator_ready() -> bool:
    return simulator_enabled() and len(
        os.getenv("AIOPS_HITL_SIMULATOR_SIGNING_KEY", "").encode("utf-8")
    ) >= 32


def _signing_key() -> bytes:
    value = os.getenv("AIOPS_HITL_SIMULATOR_SIGNING_KEY", "")
    if len(value.encode("utf-8")) < 32:
        raise IdentityError("simulator_signing_key_not_configured")
    return value.encode("utf-8")


def simulator_catalog() -> list[dict[str, Any]]:
    return [
        {
            "subject_id": "sim:" + user_id,
            "display_name": entry["display_name"],
            "groups": list(entry["groups"]),
            "roles": [role for group in entry["groups"] for role in GROUP_ROLE_MAP[group]],
            "simulated": True,
        }
        for user_id, entry in sorted(SIMULATED_IDENTITIES.items())
    ]


def issue_simulated_assertion(user_id: str, ttl_seconds: int = 300) -> tuple[str, dict[str, Any]]:
    if not simulator_enabled():
        raise IdentityError("identity_simulator_disabled")
    if user_id not in SIMULATED_IDENTITIES:
        raise IdentityError("unknown_simulated_subject")
    if type(ttl_seconds) is not int or not 30 <= ttl_seconds <= MAX_TTL_SECONDS:
        raise IdentityError("invalid_assertion_ttl")
    now = int(time.time())
    identity = SIMULATED_IDENTITIES[user_id]
    groups = list(identity["groups"])
    roles = sorted({role for group in groups for role in GROUP_ROLE_MAP[group]})
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "sim:" + user_id,
        "display_name": identity["display_name"],
        "groups": groups,
        "roles": roles,
        "iat": now,
        "nbf": now,
        "exp": now + ttl_seconds,
        "jti": _b64(os.urandom(18)),
        "simulated": True,
        "auth_method": "simulated-fixture",
        "assurance": "NONE",
        "mapping_version": "sim-groups-v1",
    }
    payload = _b64(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode())
    signature = _b64(hmac.new(_signing_key(), payload.encode(), hashlib.sha256).digest())
    return payload + "." + signature, claims


def verify_assertion(token: str, *, allow_simulated: bool = False) -> dict[str, Any]:
    if not isinstance(token, str) or token.count(".") != 1:
        raise IdentityError("invalid_identity_assertion")
    payload, supplied = token.split(".", 1)
    expected = _b64(hmac.new(_signing_key(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(supplied, expected):
        raise IdentityError("invalid_identity_signature")
    try:
        claims = json.loads(_unb64(payload))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise IdentityError("invalid_identity_payload") from exc
    now = int(time.time())
    if claims.get("iss") != ISSUER or claims.get("aud") != AUDIENCE:
        raise IdentityError("identity_issuer_or_audience_mismatch")
    if type(claims.get("exp")) is not int or claims["exp"] <= now:
        raise IdentityError("identity_assertion_expired")
    if type(claims.get("nbf")) is not int or claims["nbf"] > now:
        raise IdentityError("identity_assertion_not_yet_valid")
    if claims.get("simulated") is not True:
        raise IdentityError("identity_provenance_missing")
    if not allow_simulated:
        raise IdentityError("simulated_identity_forbidden_for_live")
    if not isinstance(claims.get("sub"), str) or not claims["sub"].startswith("sim:"):
        raise IdentityError("invalid_identity_subject")
    if not isinstance(claims.get("roles"), list) or not isinstance(claims.get("groups"), list):
        raise IdentityError("invalid_identity_entitlements")
    return claims


LIVE_ROLES = {
    "operator", "senior_operator", "storage_admin", "oncall_lead",
    "security_admin", "incident_commander",
}


def oidc_configured() -> bool:
    """Configuration presence only; this does not prove the provider is reachable."""
    return all((
        os.getenv("AIOPS_HITL_OIDC_ISSUER", "").startswith("https://"),
        bool(os.getenv("AIOPS_HITL_OIDC_AUDIENCE", "").strip()),
        os.getenv("AIOPS_HITL_OIDC_JWKS_URL", "").startswith("https://"),
        bool(os.getenv("AIOPS_HITL_OIDC_GROUP_ROLE_MAP", "").strip()),
    ))


def _oidc_group_role_map() -> dict[str, tuple[str, ...]]:
    raw = os.getenv("AIOPS_HITL_OIDC_GROUP_ROLE_MAP", "")
    if not raw:
        raise IdentityError("oidc_group_role_map_not_configured")
    try:
        value = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise IdentityError("oidc_group_role_map_invalid_json") from exc
    if not isinstance(value, dict) or not value:
        raise IdentityError("oidc_group_role_map_invalid")
    result: dict[str, tuple[str, ...]] = {}
    for group_id, roles in value.items():
        if (not isinstance(group_id, str) or not group_id.strip()
                or not isinstance(roles, list) or not roles
                or any(not isinstance(role, str) or role not in LIVE_ROLES for role in roles)):
            raise IdentityError("oidc_group_role_map_invalid")
        result[group_id] = tuple(sorted(set(roles)))
    return result


@lru_cache(maxsize=4)
def _oidc_jwks_client(jwks_url: str):
    from jwt import PyJWKClient
    return PyJWKClient(jwks_url, cache_keys=True, lifespan=300, timeout=5)


def verify_oidc_assertion(token: str) -> dict[str, Any]:
    """Verify a short-lived RS256 OIDC JWT and derive roles from immutable group IDs.

    Caller-supplied actor IDs and role names are never identity evidence. OIDC
    issuer, audience, JWKS URL and the immutable group-ID mapping are deployment
    configuration. The JWKS client caches keys briefly and requires HTTPS.
    """
    if not oidc_configured():
        raise IdentityError("oidc_identity_provider_not_configured")
    if not isinstance(token, str) or not token or len(token) > 16384:
        raise IdentityError("invalid_oidc_assertion")
    issuer = os.environ["AIOPS_HITL_OIDC_ISSUER"].strip()
    audience = os.environ["AIOPS_HITL_OIDC_AUDIENCE"].strip()
    jwks_url = os.environ["AIOPS_HITL_OIDC_JWKS_URL"].strip()
    group_claim = os.getenv("AIOPS_HITL_OIDC_GROUP_CLAIM", "groups").strip()
    try:
        import jwt
    except ImportError as exc:
        raise IdentityError("oidc_jwt_verifier_dependency_missing") from exc
    try:
        client = _oidc_jwks_client(jwks_url)
        signing_key = client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, signing_key.key, algorithms=["RS256"],
            audience=audience, issuer=issuer,
            options={"require": ["iss", "aud", "sub", "iat", "nbf", "exp", "jti"]},
            leeway=30,
        )
    except Exception as exc:
        raise IdentityError("oidc_assertion_verification_failed") from exc
    now = int(time.time())
    issued = claims.get("iat")
    expires = claims.get("exp")
    if type(issued) is not int or type(expires) is not int:
        raise IdentityError("oidc_assertion_time_claims_invalid")
    if issued > now + 30 or expires - issued > 600:
        raise IdentityError("oidc_assertion_lifetime_invalid")
    if claims.get("simulated") is True:
        raise IdentityError("simulated_identity_forbidden_for_live")
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 512:
        raise IdentityError("oidc_subject_invalid")
    jti = claims.get("jti")
    if not isinstance(jti, str) or not jti.strip() or len(jti) > 512:
        raise IdentityError("oidc_jti_invalid")
    required_amr = os.getenv("AIOPS_HITL_OIDC_REQUIRED_AMR", "mfa").strip()
    if required_amr:
        amr = claims.get("amr")
        if not isinstance(amr, list) or required_amr not in amr:
            raise IdentityError("oidc_mfa_assurance_required")
    max_auth_age = int(os.getenv("AIOPS_HITL_OIDC_MAX_AUTH_AGE_SECONDS", "300"))
    auth_time = claims.get("auth_time")
    if (type(auth_time) is not int or max_auth_age < 60
            or max_auth_age > 3600 or now - auth_time > max_auth_age
            or auth_time > now + 30):
        raise IdentityError("oidc_recent_authentication_required")
    groups = claims.get(group_claim)
    if not isinstance(groups, list) or not groups or any(
        not isinstance(group, str) or not group.strip() for group in groups
    ):
        raise IdentityError("oidc_group_claim_missing_or_invalid")
    group_map = _oidc_group_role_map()
    roles = sorted({role for group in groups for role in group_map.get(group, ())})
    if not roles:
        raise IdentityError("oidc_subject_has_no_mapped_approval_role")
    subject_id = "oidc:" + hashlib.sha256(
        json.dumps([issuer, subject], separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "issuer": issuer,
        "subject_id": subject_id,
        "display_name": str(claims.get("name") or claims.get("preferred_username") or subject)[:200],
        "groups": sorted(set(groups)),
        "roles": roles,
        "jti": jti,
        "issued_at": issued,
        "expires_at": expires,
        "mapping_version": os.getenv("AIOPS_HITL_OIDC_MAPPING_VERSION", "unversioned"),
        "auth_method": "oidc-jwks-rs256",
        "simulated": False,
    }


def require_live_assertion(token: str) -> dict[str, Any]:
    """LIVE accepts only a verified production OIDC JWT; simulator never falls back."""
    return verify_oidc_assertion(token)


def authorize_critical_approvals(approvals: list[dict[str, str]]) -> bool:
    """Two distinct immutable subjects must satisfy the two critical roles."""
    security = {
        item.get("subject_id")
        for item in approvals
        if item.get("role") == "security_admin"
    }
    commanders = {
        item.get("subject_id")
        for item in approvals
        if item.get("role") == "incident_commander"
    }
    return bool(security and commanders and not (security & commanders))


# No free-form command strings are accepted. These are logical operation IDs;
# host-specific root-owned wrappers must be implemented and qualified separately.
SUDO_ACTION_CATALOG = {
    "linux.collect_diagnostics": {"role": "operator", "risk": "LOW", "wrapper": "aiops-collect-diagnostics"},
    "linux.increase_logging": {"role": "senior_operator", "risk": "MEDIUM", "wrapper": "aiops-increase-logging"},
    "linux.restart_service": {"role": "storage_admin", "risk": "HIGH", "wrapper": "aiops-restart-service"},
}


def authorize_sudo_request(
    *, action_id: str, subject_roles: list[str], host_id: str,
    allowed_hosts: set[str], simulated: bool,
) -> dict[str, Any]:
    """Pure authorization precheck; it never executes a command or grants sudo."""
    action = SUDO_ACTION_CATALOG.get(action_id)
    if simulated:
        return {"allowed": False, "reason": "simulated_identity_cannot_execute", "execution_allowed": False}
    if not action:
        return {"allowed": False, "reason": "action_not_allowlisted", "execution_allowed": False}
    if host_id not in allowed_hosts:
        return {"allowed": False, "reason": "host_out_of_scope", "execution_allowed": False}
    if action["role"] not in set(subject_roles):
        return {"allowed": False, "reason": "required_role_missing", "execution_allowed": False}
    return {
        "allowed": True,
        "reason": "authorization_precheck_only",
        "action_id": action_id,
        "wrapper_id": action["wrapper"],
        "risk_tier": action["risk"],
        "execution_allowed": False,
    }
