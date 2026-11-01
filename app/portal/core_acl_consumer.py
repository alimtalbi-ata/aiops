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
            and hmac.compare_digest(actor.tenant_id, binding.tenant_id)
            and bool(_RUN.fullmatch(binding.run_id))
            and bool(_INCIDENT.fullmatch(binding.incident_id))
            and bool(_RESOURCE.fullmatch(binding.glpi_instance_id))
            and bool(_TICKET.fullmatch(binding.ticket_id))
            and bool(_ENTITY.fullmatch(binding.glpi_entity_id)))


def positive_core_contract_matches(payload: object, actor: PortalActorContext,
                                   binding: ServerXref, *, now: int | None = None) -> bool:
    """Future contract gate. Current Core xref v1 MUST fail this validation.

    A matching envelope alone never enables an upstream business read:
    Core's authenticated actor delegation and independent GLPI ownership
    still require an architect-qualified transport and provenance contract.
    """
    if not exact_binding_valid(actor, binding) or not isinstance(payload, dict):
        return False
    clock = int(time.time()) if now is None else now
    expected = {
        "actor_subject": actor.subject, "tenant_id": binding.tenant_id,
        "run_id": binding.run_id, "incident_id": binding.incident_id,
        "glpi_instance_id": binding.glpi_instance_id,
        "ticket_id": binding.ticket_id, "glpi_entity_id": binding.glpi_entity_id,
    }
    return (payload.get("schema") == _SCHEMA
            and payload.get("decision") == "ALLOW"
            and payload.get("permission") == "run:read"
            and payload.get("tenant_acl_qualified") is True
            and payload.get("glpi_owner_attested") is True
            and payload.get("provenance") == "AUTHENTICATED_GLPI_READBACK"
            and isinstance(payload.get("acl_version"), str)
            and bool(payload["acl_version"])
            and type(payload.get("expires_at")) is int
            and clock < payload["expires_at"] <= clock + 300
            and all(isinstance(payload.get(k), str)
                    and hmac.compare_digest(payload[k], v)
                    for k, v in expected.items()))


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
