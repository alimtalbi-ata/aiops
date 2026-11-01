"""Portal-owned Core actor-resource v1 wire preflight; NEVER dispatches network I/O.

The existing Core v1 endpoint always returns UNKNOWN. A signed synthetic
response, a service bearer, or a verified OIDC identity cannot establish GLPI
native human permission. This module cannot authorize any business read.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import time
from dataclasses import dataclass
from typing import Mapping

from portal.core_acl_consumer import (
    ServerXref, configured_core_authz_target, core_v1_envelope_matches,
    exact_binding_valid,
)
from portal.oidc_identity import (
    IdentityRejected, IdentityUnavailable, PortalActorContext,
    _decode, _json_strict, _verify_rs256,
)

_TENANT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,95}\\Z", re.ASCII)
_NONCE = re.compile(r"[A-Za-z0-9_-]{32,128}\\Z", re.ASCII)
_KID = re.compile(r"[A-Za-z0-9_.-]{1,128}\\Z", re.ASCII)
_DOMAIN = b"aiops.portal.core-actor-resource-authorization.v1\\n"
_MAX_BODY = 16384


@dataclass(frozen=True, repr=False)
class CoreAuthzWirePlan:
    """Server-only request blueprint. Not a runnable HTTP client or ACL."""
    origin: str
    path: str
    service_bearer: str
    nonce: str
    body: bytes
    dispatch_allowed: bool = False

    def __repr__(self) -> str:
        return "CoreAuthzWirePlan(<server-only, dispatch_disabled>)"

    @property
    def method(self) -> str:
        return "POST"

    @property
    def headers(self) -> dict[str, str]:
        # NEVER send these to a browser; this is a server-only contract fixture.
        return {"Authorization": "Bearer " + self.service_bearer,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Cache-Control": "no-store"}


def prepare_core_authz_wire(actor: PortalActorContext, binding: ServerXref, *,
                            env: Mapping[str, str] | None = None,
                            now: int | None = None) -> CoreAuthzWirePlan | None:
    """Construct a bounded, exact-resource request without any HTTP call.

    No actor delegation token is available or fabricated. Dispatch remains
    disabled until Core and GLPI owners attest a real delegation, native human
    permissions, independent ownership, and durable nonce/revocation ledger.
    """
    clock = int(time.time()) if now is None else now
    target = configured_core_authz_target(env)
    if (type(clock) is not int or target is None
            or not exact_binding_valid(actor, binding)
            or not _TENANT.fullmatch(binding.tenant_id)
            or actor.expires_at <= clock):
        return None
    nonce = secrets.token_urlsafe(32)
    if _NONCE.fullmatch(nonce) is None:
        return None
    body = json.dumps({
        "incident_id": binding.incident_id,
        "glpi_instance_id": binding.glpi_instance_id,
        "ticket_id": binding.ticket_id,
        "glpi_entity_id": binding.glpi_entity_id,
        "permission": "run:read",
        "nonce": nonce,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    if len(body) > _MAX_BODY:
        return None
    return CoreAuthzWirePlan(
        target.origin,
        "/api/tenants/" + binding.tenant_id + "/runs/" + binding.run_id
        + "/actor-resource-authorization",
        target.service_token, nonce, body,
    )


def _canonical_signed_bytes(origin: str, payload: dict) -> bytes:
    """Domain-separate the Core response signature and bind it to the origin."""
    return (_DOMAIN + origin.encode("ascii") + b"\\n"
            + json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii"))


def verify_pinned_core_response_signature(
        payload: object, signature: object, *,
        actor: PortalActorContext, binding: ServerXref,
        plan: CoreAuthzWirePlan,
        env: Mapping[str, str] | None = None,
        now: int | None = None) -> bool:
    """Offline signature and exact nonce verifier, NOT an authorization grant.

    Signature wire proposal: {alg: RS256, kid: pinned JWK kid,
    signature: unpadded base64url}. The signature covers a domain-separated,
    canonical JSON response and the pinned HTTPS Core origin. No dynamic JWK
    URLs, browser headers, shared bearer, or Core fetch are accepted.
    """
    settings = os.environ if env is None else env
    if (not isinstance(plan, CoreAuthzWirePlan)
            or plan.dispatch_allowed is not False
            or not isinstance(payload, dict)
            or not isinstance(signature, dict)
            or set(signature) != {"alg", "kid", "signature"}
            or signature["alg"] != "RS256"
            or not isinstance(signature["kid"], str)
            or _KID.fullmatch(signature["kid"]) is None
            or not isinstance(signature["signature"], str)
            or not core_v1_envelope_matches(
                payload, actor, binding, request_nonce=plan.nonce, now=now)):
        return False
    target = configured_core_authz_target(settings)
    if (target is None or target.origin != plan.origin
            or target.service_token != plan.service_bearer
            or not plan.path.endswith("/actor-resource-authorization")
            or plan.path != "/api/tenants/" + binding.tenant_id
            + "/runs/" + binding.run_id + "/actor-resource-authorization"):
        return False
    try:
        raw = settings.get("AIOPS_PORTAL_CORE_AUTHZ_RESPONSE_JWKS_JSON", "")
        if not isinstance(raw, str) or len(raw) > 32768:
            return False
        jwks = _json_strict(raw)
        if (not isinstance(jwks, dict) or set(jwks) != {"keys"}
                or not isinstance(jwks["keys"], list)):
            return False
        signed = _canonical_signed_bytes(plan.origin, payload)
        if len(signed) > _MAX_BODY:
            return False
        _verify_rs256(signed, _decode(signature["signature"]),
                      signature["kid"], jwks)
        return True
    except (IdentityRejected, IdentityUnavailable, ValueError, TypeError,
            KeyError, UnicodeError, OverflowError):
        return False


def core_authz_read_permitted(*_args: object, **_kwargs: object) -> bool:
    """Permanent fail-closed activation fence until a separately reviewed PR."""
    return False
