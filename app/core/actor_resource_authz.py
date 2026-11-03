"""Core-only actor delegation preflight; no positive business ACL without GLPI native rights.

The independently authenticated IdP introspection is necessary, NOT sufficient.
A service bearer, OIDC claims, HMAC xref and GLPI service readback never grant
an actor permission to see a ticket or CI. No ALLOW is emitted in v1 until
the separately authenticated GLPI native actor-permission adapter is qualified.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from core import itsm_xref as x

router = APIRouter()
SCHEMA = "aiops.core-actor-resource-authorization.v1"
_RUN = re.compile(r"RUN-[A-Za-z0-9_-]{1,96}\Z", re.ASCII)
_INC = re.compile(r"INC-[A-Za-z0-9_-]{1,96}\Z", re.ASCII)
_NONCE = re.compile(r"[A-Za-z0-9_-]{24,128}\Z", re.ASCII)
_ENTITY = re.compile(r"[0-9]{1,18}\Z", re.ASCII)
_SUBJECT = re.compile(r"[\x21-\x7e]{1,256}\Z", re.ASCII)
_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}


def _reply(code=200, decision="UNKNOWN"):
    headers = dict(_HEADERS)
    if code == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse({"schema": SCHEMA, "decision": decision},
                        status_code=code, headers=headers)


def _actor_introspection(delegation, expected, now):
    """Use server-authenticated HTTPS OAuth2 introspection on every request.

    This is a live revocation check, not a local JWT/HMAC or Portal claim.
    An issuer must supply a resource-bound, short-lived opaque access token.
    No network call is made without a pinned operator-owned configuration.
    """
    raw = os.getenv("AIOPS_XREF_ACTOR_INTROSPECTION_JSON", "")
    if not raw or len(raw) > 8192 or not isinstance(delegation, str):
        return None
    if not 16 <= len(delegation) <= 4096 or not delegation.isascii() or any(
            c.isspace() or not c.isprintable() for c in delegation):
        return None
    try:
        cfg = json.loads(raw)
        if not isinstance(cfg, dict) or set(cfg) != {
                "url", "issuer", "audience", "client_id", "client_secret"}:
            return None
        url = cfg["url"]
        parsed = urlsplit(url)
        if (not isinstance(url, str) or len(url) > 512
                or parsed.scheme != "https" or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path in ("", "/") or parsed.port not in (None, 443, 8443)
                or parsed.geturl() != url):
            return None
        if (not all(isinstance(cfg[k], str) and 1 <= len(cfg[k]) <= 256
                    and cfg[k].isascii() and cfg[k].isprintable()
                    for k in ("issuer", "audience", "client_id", "client_secret"))
                or len(cfg["client_secret"]) < 32):
            return None
        with requests.Session() as session:
            session.trust_env = False
            with session.post(
                    url, data={"token": delegation, "token_type_hint": "access_token"},
                    auth=(cfg["client_id"], cfg["client_secret"]),
                    headers={"Accept": "application/json"},
                    timeout=(2, 3), allow_redirects=False, stream=True,
                    verify=True) as response:
                if (response.status_code != 200 or
                        response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                        != "application/json"):
                    return None
                data = bytearray()
                for chunk in response.iter_content(chunk_size=4096):
                    data.extend(chunk)
                    if len(data) > 16384:
                        return None
                claims = json.loads(data.decode("utf-8"))
        if not isinstance(claims, dict):
            return None
        # A mock 'verified=true', unsigned subject or service token is not authority.
        if claims.get("active") is not True or claims.get("revoked") is not False:
            return None
        if (claims.get("iss") != cfg["issuer"] or
                claims.get("aud") != cfg["audience"] or
                not isinstance(claims.get("sub"), str) or
                not _SUBJECT.fullmatch(claims["sub"])):
            return None
        if (type(claims.get("iat")) is not int or
                type(claims.get("nbf")) is not int or
                type(claims.get("exp")) is not int or
                not now - 300 <= claims["iat"] <= now or
                not claims["iat"] <= claims["nbf"] <= now < claims["exp"] <= now + 300):
            return None
        if (not isinstance(claims.get("jti"), str)
                or not _NONCE.fullmatch(claims["jti"])
                or type(claims.get("glpi_user_id")) is not int
                or claims["glpi_user_id"] < 1):
            return None
        if (not isinstance(claims.get("permissions"), list)
                or "run:read" not in claims["permissions"]
                or any(not isinstance(p, str) for p in claims["permissions"])):
            return None
        # Custom exact-resource grants MUST come from the authenticated issuer,
        # not from a Portal-provided subject, tenant or ticket header.
        for key, value in expected.items():
            if claims.get(key) != value or type(claims.get(key)) is not type(value):
                return None
        return claims
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            requests.RequestException):
        return None


@router.post("/api/tenants/{tenant_id}/runs/{run_id}/actor-resource-authorization")
def authorize_actor_resource(
        tenant_id: str, run_id: str, payload: dict,
        authorization: str | None = Header(default=None),
        x_actor_delegation: str | None = Header(default=None)):
    """Non-enumerating Core actor ACL preflight; v1 deliberately has no ALLOW.

    GLPI native user/profile/entity rights and durable nonce consumption are
    not independently qualified. Never promote xref VERIFIED to actor ALLOW.
    """
    actor, code = x._auth(authorization)
    if code != 200:
        return _reply(code)
    if ("actor:resource:authorize" not in actor["permissions"]
            or tenant_id not in actor["tenant_ids"]):
        return _reply(403, "UNAUTHORIZED")
    if not isinstance(payload, dict) or set(payload) != {
            "incident_id", "glpi_instance_id", "ticket_id", "glpi_entity_id",
            "permission", "nonce"}:
        return _reply()
    instance = payload["glpi_instance_id"]
    ticket = payload["ticket_id"]
    entity = payload["glpi_entity_id"]
    if (not x._valid(tenant_id) or not x._valid(run_id, _RUN)
            or not x._valid(payload["incident_id"], _INC)
            or not x._valid(instance) or not x._valid(ticket, x._TICKET)
            or not isinstance(entity, str) or not _ENTITY.fullmatch(entity)
            or payload["permission"] != "run:read"
            or not isinstance(payload["nonce"], str)
            or not _NONCE.fullmatch(payload["nonce"])):
        return _reply()
    expected = {"tenant_id": tenant_id, "run_id": run_id,
                "incident_id": payload["incident_id"], "glpi_instance_id": instance,
                "ticket_id": ticket, "glpi_entity_id": entity,
                "permission": "run:read", "nonce": payload["nonce"]}
    now = int(datetime.now(timezone.utc).timestamp())
    claims = _actor_introspection(x_actor_delegation, expected, now)
    if claims is None:
        return _reply()
    key = x._key()
    if key is None:
        return _reply(503)
    try:
        with x.db() as c:
            rows = c.execute(
                "select " + ",".join(x._COLUMNS) + " from aiops.itsm_xref_events "
                "where tenant_id=%s and glpi_instance_id=%s and ticket_id=%s "
                "order by mapping_version asc limit 33",
                (tenant_id, instance, ticket)).fetchall()
            status, record = x._evaluate(
                c, rows, tenant_id, instance, ticket, key,
                datetime.now(timezone.utc))
    except Exception:
        return _reply(503)
    if (status != "VERIFIED" or record is None
            or record["run_id"] != run_id
            or record["incident_id"] != payload["incident_id"]
            or record["glpi_entity_id"] != entity):
        return _reply()
    # Native GLPI reads use an actor session and an independently keyed,
    # source-authenticated subject mapping, never the service GLPI session.
    from core import actor_native_authority as native
    if not native._native_glpi_preflight(claims, expected, now):
        return _reply()
    # Independent Core Incident/Run/source-event readback is distinct from
    # IdP introspection, the signed xref and native GLPI human rights.
    # Missing/unqualified source => UNKNOWN before any nonce consumption.
    from core import actor_run_event_source
    if not actor_run_event_source._source_run_event_preflight(claims, expected, record, now):
        return _reply()
    # The source-contract pass alone cannot grant rights. Consume a durable,
    # issuer/JTI-serialized nonce only after the independently authenticated
    # source preflight; revoked, replayed or cross-tenant grants stay UNKNOWN.
    from core import actor_replay_fence
    consumed = actor_replay_fence.consume_actor_delegation(claims, expected, now)
    if consumed is None:
        return _reply(503)
    # Even first consumption + synthetic GLPI/IdP mocks is NOT an ALLOW.
    # Real issuer trust, GLPI native ticket:read and operator signoff remain
    # separately required before any future positive authorization contract.
    return _reply()
