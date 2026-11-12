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

from fastapi import Request
from portal.oidc_session import _session_from_cookie

from portal.core_acl_consumer import (
    ServerXref, configured_core_authz_target, core_v1_envelope_matches,
    exact_binding_valid,
)
from portal.oidc_identity import (
    IdentityRejected, IdentityUnavailable, PortalActorContext,
    _decode, _json_strict, _verify_rs256,
)

_TENANT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,95}\Z", re.ASCII)
_NONCE = re.compile(r"[A-Za-z0-9_-]{32,128}\Z", re.ASCII)
_KID = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z", re.ASCII)
_DOMAIN = b"aiops.portal.core-actor-resource-authorization.v1\n"
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
    return (_DOMAIN + origin.encode("ascii") + b"\n"
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


# This is the response Core #246/#250 actually emits today. It is deliberately
# different from the proposed future detached-RS256 ALLOW envelope above.
_CORE_CURRENT_SCHEMA = "aiops.core-actor-resource-authorization.v1"
_CORE_CURRENT_DECISIONS = {200: "UNKNOWN", 401: "UNKNOWN",
                           403: "UNAUTHORIZED", 503: "UNKNOWN"}


def core_v1_current_unknown_reply_matches(status_code: object, payload: object,
                                          headers: Mapping[str, str]) -> bool:
    """Strict offline compatibility check for Core's *negative* v1 response.

    The Core endpoint currently returns only {schema, decision}, no signed
    actor/tenant/resource proof, nonce echo, issuer, GLPI rights or ALLOW.
    A matching 200 UNKNOWN is NEVER an ACL grant. This function does not
    dispatch I/O, consume a nonce, or authorize any business read.
    """
    if (type(status_code) is not int
            or status_code not in _CORE_CURRENT_DECISIONS
            or type(payload) is not dict
            or set(payload) != {"schema", "decision"}
            or payload["schema"] != _CORE_CURRENT_SCHEMA
            or payload["decision"] != _CORE_CURRENT_DECISIONS[status_code]
            or not isinstance(headers, Mapping)):
        return False
    normalized: dict[str, str] = {}
    for key, value in headers.items():
        if not isinstance(key, str) or not isinstance(value, str):
            return False
        lower = key.lower()
        if lower in normalized and normalized[lower] != value:
            return False
        normalized[lower] = value
    return all(normalized.get(key) == value for key, value in {
        "cache-control": "no-store",
        "pragma": "no-cache",
        "x-content-type-options": "nosniff",
        "referrer-policy": "no-referrer",
    }.items()) and (status_code != 401
                   or normalized.get("www-authenticate") == "Bearer")


@dataclass(frozen=True)
class OfflineCoreReplyAssessment:
    """Contract-test observation only; never an authorization decision."""
    kind: str
    portal_status: int = 503
    state: str = "UNKNOWN"
    read_permitted: bool = False


def assess_core_authz_reply_offline(
        status_code: object, payload: object, headers: Mapping[str, str],
        signature: object, *, actor: PortalActorContext, binding: ServerXref,
        plan: CoreAuthzWirePlan,
        env: Mapping[str, str] | None = None,
        now: int | None = None) -> OfflineCoreReplyAssessment:
    """Reconcile actual Core denial and proposed signed ALLOW *without I/O*.

    A correctly signed synthetic ALLOW is merely a future wire-shape match.
    There is no Core-issued signing contract, native GLPI human ACL, or durable
    replay ledger. Both matching cases remain 503 UNKNOWN, not CONNECTED.
    """
    invalid = OfflineCoreReplyAssessment("INVALID")
    clock = int(time.time()) if now is None else now
    if (type(clock) is not int
            or not isinstance(actor, PortalActorContext)
            or actor.expires_at <= clock
            or not isinstance(plan, CoreAuthzWirePlan)
            or plan.dispatch_allowed is not False
            or not exact_binding_valid(actor, binding)
            or not isinstance(headers, Mapping)):
        return invalid
    # Even negative Core parity is tied to the server-built, pinned request.
    # Never accept a caller-fabricated plan with another tenant/Run or nonce.
    target = configured_core_authz_target(env)
    if (target is None or target.origin != plan.origin
            or target.service_token != plan.service_bearer
            or plan.path != "/api/tenants/" + binding.tenant_id
            + "/runs/" + binding.run_id + "/actor-resource-authorization"
            or not isinstance(plan.nonce, str)
            or _NONCE.fullmatch(plan.nonce) is None
            or not isinstance(plan.body, bytes) or len(plan.body) > _MAX_BODY):
        return invalid
    try:
        request_body = _json_strict(plan.body)
        expected = {
            "incident_id": binding.incident_id,
            "glpi_instance_id": binding.glpi_instance_id,
            "ticket_id": binding.ticket_id,
            "glpi_entity_id": binding.glpi_entity_id,
            "permission": "run:read",
            "nonce": plan.nonce,
        }
        if (type(request_body) is not dict or request_body != expected
                or json.dumps(request_body, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=True).encode("ascii") != plan.body):
            return invalid
    except (IdentityRejected, IdentityUnavailable, ValueError, TypeError,
            UnicodeError, OverflowError):
        return invalid
    normalized: dict[str, str] = {}
    for key, value in headers.items():
        if not isinstance(key, str) or not isinstance(value, str):
            return invalid
        lowered = key.lower()
        if lowered in normalized:
            return invalid
        normalized[lowered] = value
    if (any(normalized.get(k) != v for k, v in {
            "cache-control": "no-store",
            "pragma": "no-cache",
            "x-content-type-options": "nosniff",
            "referrer-policy": "no-referrer",
        }.items())
            or any(k in normalized for k in (
                "set-cookie", "location", "access-control-allow-origin",
                "x-actor-id", "x-tenant-id", "x-glpi-profile"))):
        return invalid
    # Current Core replies are *unsigned*, strictly negative, and can include
    # HTTP 200 UNKNOWN. A 200 is never a positive ACL.
    if signature is None and core_v1_current_unknown_reply_matches(
            status_code, payload, headers):
        return OfflineCoreReplyAssessment("CURRENT_CORE_NEGATIVE")
    # Future ALLOW is only a proposed signed shape. The Core owner has not
    # agreed to emit it; no nonce consumption or GLPI proof is implemented.
    if (type(status_code) is int and status_code == 200
            and verify_pinned_core_response_signature(
                payload, signature, actor=actor, binding=binding, plan=plan,
                env=env, now=clock)):
        return OfflineCoreReplyAssessment("SIGNED_SHAPE_UNQUALIFIED")
    return invalid


def assess_core_negative_for_session(
        request: Request, *, binding: ServerXref, plan: CoreAuthzWirePlan,
        status_code: object, payload: object, headers: Mapping[str, str],
        env: Mapping[str, str] | None = None,
        now: int | None = None) -> OfflineCoreReplyAssessment:
    """Server-side *negative-only* consumer for a disposable Core reply.

    Re-resolve the identity from the revocable server session at consumption
    time, not from a browser-supplied actor/tenant or a previously captured
    actor object. A Core 200 UNKNOWN is never a grant. This function performs
    NO I/O, does not dispatch the plan, and cannot authorize business GETs.
    In particular, even a valid future signed ALLOW is INVALID here.
    """
    clock = int(time.time()) if now is None else now
    if type(clock) is not int or not isinstance(request, Request):
        return OfflineCoreReplyAssessment("SESSION_REQUIRED", portal_status=401)
    session = _session_from_cookie(request)
    if (session is None or session.expires <= clock
            or session.identity.expires_at <= clock):
        return OfflineCoreReplyAssessment("SESSION_REQUIRED", portal_status=401)
    # Never accept a detached signature/ALLOW or infer native GLPI rights.
    assessment = assess_core_authz_reply_offline(
        status_code, payload, headers, None, actor=session.identity,
        binding=binding, plan=plan, env=env, now=clock)
    if assessment.kind != "CURRENT_CORE_NEGATIVE":
        return OfflineCoreReplyAssessment("INVALID")
    return assessment
