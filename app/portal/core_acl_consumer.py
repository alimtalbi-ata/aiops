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


def core_v1_claims_match(payload: object, actor: PortalActorContext,
                         binding: ServerXref, *, nonce: str,
                         now: int | None = None) -> bool:
    """Strict *shape-only* review of a proposed v1 Core decision.

    A JSON envelope, even with every field set to ALLOW, is NOT authenticated
    Core delegation or GLPI source readback. Never use this function to grant
    access, select a Run, or initiate an upstream read. The Core owner must
    publish and qualify the actual transport, response authenticity and
    revocation semantics before any network consumer is enabled.
    """
    if not exact_binding_valid(actor, binding) or not isinstance(payload, dict):
        return False
    if not isinstance(nonce, str) or not 32 <= len(nonce) <= 128 or not nonce.isascii():
        return False
    clock = int(time.time()) if now is None else now
    if type(clock) is not int or actor.expires_at <= clock:
        return False
    expected = {
        "actor_subject": actor.subject, "tenant_id": binding.tenant_id,
        "run_id": binding.run_id, "incident_id": binding.incident_id,
        "glpi_instance_id": binding.glpi_instance_id,
        "ticket_id": binding.ticket_id, "glpi_entity_id": binding.glpi_entity_id,
        "request_nonce": nonce,
    }
    required = set(expected) | {
        "schema", "decision", "permission", "tenant_acl_qualified",
        "glpi_owner_attested", "provenance", "acl_version",
        "authorized_at", "expires_at", "revocation_checked_at",
        "decision_id", "delegation", "glpi_readback",
    }
    if set(payload) != required:
        return False
    issued, expires, checked = (payload.get(k) for k in (
        "authorized_at", "expires_at", "revocation_checked_at"))
    if (any(type(v) is not int for v in (issued, expires, checked))
            or not clock - 30 <= issued <= checked <= clock
            or not clock < expires <= min(clock + 60, actor.expires_at)):
        return False
    delegation = payload.get("delegation")
    glpi = payload.get("glpi_readback")
    if (not isinstance(delegation, dict)
            or set(delegation) != {"subject", "tenant_id", "issuer",
                                   "audience", "status", "revoked"}
            or delegation.get("status") != "VERIFIED"
            or delegation.get("revoked") is not False
            or not isinstance(glpi, dict)
            or set(glpi) != {"instance_id", "ticket_id", "entity_id",
                             "source", "verified"}
            or glpi.get("source") != "AUTHENTICATED_GLPI_READBACK"
            or glpi.get("verified") is not True):
        return False
    delegation_expected = {"subject": actor.subject,
                           "tenant_id": binding.tenant_id,
                           "issuer": actor.issuer, "audience": actor.audience}
    glpi_expected = {"instance_id": binding.glpi_instance_id,
                     "ticket_id": binding.ticket_id,
                     "entity_id": binding.glpi_entity_id}
    return (payload.get("schema") == _SCHEMA
            and payload.get("decision") == "ALLOW"
            and payload.get("permission") == "run:read"
            and payload.get("tenant_acl_qualified") is True
            and payload.get("glpi_owner_attested") is True
            and payload.get("provenance") == "AUTHENTICATED_GLPI_READBACK"
            and isinstance(payload.get("acl_version"), str)
            and bool(_RESOURCE.fullmatch(payload["acl_version"]))
            and isinstance(payload.get("decision_id"), str)
            and bool(_RESOURCE.fullmatch(payload["decision_id"]))
            and all(isinstance(payload.get(k), str)
                    and hmac.compare_digest(payload[k], v)
                    for k, v in expected.items())
            and all(isinstance(delegation.get(k), str)
                    and hmac.compare_digest(delegation[k], v)
                    for k, v in delegation_expected.items())
            and all(isinstance(glpi.get(k), str)
                    and hmac.compare_digest(glpi[k], v)
                    for k, v in glpi_expected.items()))


def positive_core_contract_matches(payload: object, actor: PortalActorContext,
                                   binding: ServerXref, *, now: int | None = None) -> bool:
    """No positive Core actor authorization exists on the current candidate.

    The legacy helper used to accept an entirely client-forgeable JSON shape.
    Keep its API but make it unconditionally fail-closed until the Core owner
    publishes an authenticated, nonce-bound and revocation-aware v1 contract
    with independently verified GLPI ownership.
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
    _ = (run_id, configured_core_target(env))
    return 503, "TENANT_ACL_NOT_QUALIFIED"
