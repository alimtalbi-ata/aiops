"""Portal-only, server-side exact Run authorization consumer (P0 fail-closed).

Core #233's xref read is service-authorized, NOT delegated to an OIDC
subject. Its synthetic GLPI ownership proof is not an independent GLPI
readback. Never call that endpoint as an actor ACL, even when configured.
The first Core request will be allowed only after a separate versioned
actor-bound authorization contract and independently authenticated GLPI
ownership are qualified. No browser bearer/header/query is an authority.
"""
from __future__ import annotations

import hmac
import os
import re
import time
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit

from fastapi import Request

from portal.oidc_identity import PortalActorContext
from portal.oidc_session import _session_from_cookie

_RUN = re.compile(r"RUN-[A-Za-z0-9_-]{1,96}\Z", re.ASCII)
_INCIDENT = re.compile(r"INC-[A-Za-z0-9_-]{1,96}\Z", re.ASCII)
_RESOURCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,95}\Z", re.ASCII)
_TICKET = re.compile(r"[1-9][0-9]{0,17}\Z", re.ASCII)
_ENTITY = re.compile(r"[0-9]{1,18}\Z", re.ASCII)
_SCOPE = "itsm:xref:read"
_SCHEMA = "aiops.core-actor-resource-authorization.v1"


@dataclass(frozen=True)
class CoreTarget:
    """Validated internal configuration; token never leaves this process."""
    origin: str
    service_token: str

    def __repr__(self) -> str:
        return "CoreTarget(origin=<pinned>, service_token=<redacted>)"


@dataclass(frozen=True)
class ServerXref:
    """Server-owned exact resource binding; never populated from browser claims."""
    tenant_id: str
    run_id: str
    incident_id: str
    glpi_instance_id: str
    ticket_id: str
    glpi_entity_id: str


def configured_core_target(env: Mapping[str, str] | None = None) -> CoreTarget | None:
    """Reject unpinned, proxied, redirected or shared bearer destinations."""
    settings = os.environ if env is None else env
    origin = settings.get("AIOPS_PORTAL_CORE_XREF_ORIGIN", "")
    token = settings.get("AIOPS_PORTAL_CORE_XREF_SERVICE_TOKEN", "")
    try:
        u = urlsplit(origin)
        valid_origin = (u.scheme == "https" and bool(u.hostname)
                        and u.hostname == u.hostname.lower()
                        and not u.hostname.endswith(".")
                        and not u.username and not u.password
                        and u.path in ("", "/") and not u.query and not u.fragment
                        and u.port in (None, 443, 8443))
    except (ValueError, TypeError, AttributeError):
        valid_origin = False
    if (not valid_origin or not isinstance(token, str)
            or not 32 <= len(token) <= 256 or not token.isascii()
            or not token.isprintable() or any(ch.isspace() for ch in token)
            or token in (settings.get("AIOPS_PORTAL_READ_TOKEN", ""),
                         settings.get("AIOPS_PORTAL_OPERATOR_TOKEN", ""),
                         settings.get("AIOPS_INTERNAL_TOKEN", ""))
            or settings.get("AIOPS_PORTAL_CORE_XREF_SCOPE") != _SCOPE):
        return None
    return CoreTarget(origin.rstrip("/"), token)


def exact_binding_valid(actor: PortalActorContext, binding: ServerXref) -> bool:
    """Validate a server-derived resource selection, never infer from Run text."""
    return (isinstance(actor, PortalActorContext)
            and actor.tenant_acl_qualified is False
            and isinstance(binding, ServerXref)
            and isinstance(actor.tenant_id, str)
            and isinstance(binding.tenant_id, str)
            and hmac.compare_digest(actor.tenant_id, binding.tenant_id)
            and all(isinstance(value, str) for value in (
                binding.run_id, binding.incident_id, binding.glpi_instance_id,
                binding.ticket_id, binding.glpi_entity_id))
            and bool(_RUN.fullmatch(binding.run_id))
            and bool(_INCIDENT.fullmatch(binding.incident_id))
            and bool(_RESOURCE.fullmatch(binding.glpi_instance_id))
            and bool(_TICKET.fullmatch(binding.ticket_id))
            and bool(_ENTITY.fullmatch(binding.glpi_entity_id)))


def configured_core_authz_target(env: Mapping[str, str] | None = None) -> CoreTarget | None:
    """Separate, least-privilege future authorization channel (no I/O).

    Reuse the strict pinned-origin validator; never reuse the xref read token.
    This preflight alone NEVER activates a Core request or a positive ACL.
    """
    settings = os.environ if env is None else env
    if settings.get("AIOPS_PORTAL_CORE_AUTHZ_SCOPE") != "actor:resource:authorize":
        return None
    authz_token = settings.get("AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN", "")
    if not authz_token or authz_token == settings.get("AIOPS_PORTAL_CORE_XREF_SERVICE_TOKEN", ""):
        return None
    shadow = dict(settings)
    shadow["AIOPS_PORTAL_CORE_XREF_ORIGIN"] = settings.get("AIOPS_PORTAL_CORE_AUTHZ_ORIGIN", "")
    shadow["AIOPS_PORTAL_CORE_XREF_SERVICE_TOKEN"] = authz_token
    shadow["AIOPS_PORTAL_CORE_XREF_SCOPE"] = _SCOPE
    return configured_core_target(shadow)


def core_v1_envelope_matches(payload: object, actor: PortalActorContext,
                             binding: ServerXref, *, request_nonce: str,
                             now: int | None = None) -> bool:
    """Strict *shape* check for the proposed Core actor-resource v1 contract.

    A JSON envelope is not a signed delegation, verified GLPI authority or
    an ACL grant. This function is deliberately never used to allow reads.
    Core must first publish/qualify authenticated subject delegation and an
    independent GLPI ownership + native actor permission readback.
    """
    if (not exact_binding_valid(actor, binding) or not isinstance(payload, dict)
            or not isinstance(request_nonce, str)
            or re.fullmatch(r"[A-Za-z0-9_-]{32,128}", request_nonce) is None):
        return False
    keys = {
        "schema", "decision", "permission", "tenant_acl_qualified",
        "acl_version", "decision_id", "actor_subject", "actor_issuer",
        "actor_audience", "tenant_id", "run_id", "incident_id",
        "glpi_instance_id", "ticket_id", "glpi_entity_id", "request_nonce",
        "issued_at", "expires_at", "revocation_checked_at", "revoked",
        "delegation", "glpi_readback",
    }
    if set(payload) != keys:
        return False
    clock = int(time.time()) if now is None else now
    if type(clock) is not int:
        return False
    expected = {
        "actor_subject": actor.subject, "actor_issuer": actor.issuer,
        "actor_audience": actor.audience, "tenant_id": binding.tenant_id,
        "run_id": binding.run_id, "incident_id": binding.incident_id,
        "glpi_instance_id": binding.glpi_instance_id,
        "ticket_id": binding.ticket_id, "glpi_entity_id": binding.glpi_entity_id,
        "request_nonce": request_nonce,
    }
    if not all(isinstance(payload.get(k), str)
               and hmac.compare_digest(payload[k], v)
               for k, v in expected.items()):
        return False
    if (payload["schema"] != _SCHEMA or payload["decision"] != "ALLOW"
            or payload["permission"] != "run:read"
            or payload["tenant_acl_qualified"] is not True
            or payload["revoked"] is not False
            or not isinstance(payload["acl_version"], str)
            or re.fullmatch(r"v[1-9][0-9]{0,3}", payload["acl_version"]) is None
            or not isinstance(payload["decision_id"], str)
            or re.fullmatch(r"[A-Za-z0-9_-]{16,128}", payload["decision_id"]) is None):
        return False
    issued, expiry, revocation = (payload.get(k) for k in
                                 ("issued_at", "expires_at", "revocation_checked_at"))
    if (any(type(v) is not int for v in (issued, expiry, revocation))
            or not clock - 60 <= issued <= clock
            or not clock < expiry <= min(clock + 60, actor.expires_at)
            or not clock - 30 <= revocation <= clock
            or revocation < issued):
        return False
    delegation, glpi = payload["delegation"], payload["glpi_readback"]
    if (not isinstance(delegation, dict) or set(delegation) != {
            "kind", "subject", "issuer", "audience", "tenant_id",
            "expires_at", "revoked"}):
        return False
    if (delegation["kind"] != "CORE_VERIFIED_OIDC_DELEGATION"
            or delegation["revoked"] is not False
            or type(delegation["expires_at"]) is not int
            or delegation["expires_at"] < expiry
            or any(not isinstance(delegation.get(k), str)
                   or not hmac.compare_digest(delegation[k], v)
                   for k, v in {
                       "subject": actor.subject, "issuer": actor.issuer,
                       "audience": actor.audience, "tenant_id": binding.tenant_id,
                   }.items())):
        return False
    if (not isinstance(glpi, dict) or set(glpi) != {
            "kind", "instance_id", "ticket_id", "entity_id", "permission",
            "verified_at", "expires_at", "ownership_confirmed",
            "actor_permission_confirmed", "run_ticket_binding_confirmed"}):
        return False
    if (glpi["kind"] != "INDEPENDENT_AUTHENTICATED_GLPI_READBACK"
            or glpi["permission"] != "ticket:read"
            or glpi["ownership_confirmed"] is not True
            or glpi["actor_permission_confirmed"] is not True
            or glpi["run_ticket_binding_confirmed"] is not True
            or type(glpi["verified_at"]) is not int
            or type(glpi["expires_at"]) is not int
            or not clock - 60 <= glpi["verified_at"] <= clock
            or glpi["expires_at"] < expiry
            or any(not isinstance(glpi.get(k), str)
                   or not hmac.compare_digest(glpi[k], v)
                   for k, v in {
                       "instance_id": binding.glpi_instance_id,
                       "ticket_id": binding.ticket_id,
                       "entity_id": binding.glpi_entity_id,
                   }.items())):
        return False
    return True


def positive_core_contract_matches(payload: object, actor: PortalActorContext,
                                   binding: ServerXref, *, now: int | None = None) -> bool:
    """Deliberately NOT an ALLOW: Core has not published qualified v1.

    Retain this historical API as a permanent negative gate so callers
    cannot accidentally promote a future-shaped or synthetic JSON fixture.
    A new reviewed authenticated transport + GLPI proof consumer is required.
    """
    _ = (payload, actor, binding, now)
    return False


def consume_run_acl(request: Request, run_id: str, *,
                    env: Mapping[str, str] | None = None) -> tuple[int, str]:
    """OIDC session identity is necessary, never sufficient.

    No upstream request is made: Core #233 has no OIDC subject-bound
    delegation, nor independently attested GLPI ownership. Do not use
    shared service token, browser bearer, role headers or forged IDs as ACL.
    Uniform 503 for present/foreign/absent/invalid Run IDs avoids oracles.
    """
    session = _session_from_cookie(request)
    if session is None:
        return 401, "OIDC_SESSION_REQUIRED"
    actor = session.identity
    now = int(time.time())
    if (not isinstance(actor, PortalActorContext)
            or actor.tenant_acl_qualified is not False
            or not actor.subject or not actor.tenant_id
            or not actor.roles or actor.expires_at <= now
            or session.expires <= now):
        return 401, "OIDC_SESSION_REQUIRED"
    # A valid session and configured service token cannot qualify a Run.
    # Never use run_id to construct an upstream URL before ACL.
    _ = (run_id, configured_core_target(env), configured_core_authz_target(env))
    return 503, "TENANT_ACL_NOT_QUALIFIED"
