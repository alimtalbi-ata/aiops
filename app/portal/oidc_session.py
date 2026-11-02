"""Portal-only OIDC code+PKCE handshake and revocable, non-authorizing sessions.

Server-owned ephemeral store, deliberately fail-closed across workers/restarts.
No browser bearer/actor/tenant claim is accepted. A session is NOT Core ACL.
No Core, GLPI, Twin, NOC, Copilot or other business upstream is called here.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import NamedTuple

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from portal.oidc_identity import (
    IdentityRejected, IdentityUnavailable, PortalActorContext,
    _json_strict, verify_server_oidc_assertion,
)

router = APIRouter()
_STATE_COOKIE = "__Host-aiops_portal_oidc_state"
_SESSION_COOKIE = "__Host-aiops_portal_session"
_MAX_PENDING = 1024
_MAX_SESSIONS = 2048
_STATE_TTL = 300
_SESSION_TTL = 900
_CODE = re.compile(r"[A-Za-z0-9._~-]{1,2048}\Z")
_OPAQUE = re.compile(r"[A-Za-z0-9_-]{32,128}\Z")
_lock = threading.RLock()


class _Pending(NamedTuple):
    verifier: str
    nonce: str
    expires: int


class _Session(NamedTuple):
    identity: PortalActorContext
    expires: int


_pending: dict[str, _Pending] = {}
_sessions: dict[str, _Session] = {}


@dataclass(frozen=True)
class _Config:
    issuer: str
    authorize: str
    token: str
    client: str
    redirect: str
    origin: str


def _origin(url: str, *, portal_redirect: bool = False) -> str:
    """Only the Portal callback may use explicit HTTPS :7777 (not :17777).

    Configuration validation is not a claim that a host listener exists.
    """
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
        if (parsed.scheme != "https" or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment
                or (port is not None and (not portal_redirect or port != 7777))
                or parsed.hostname.endswith(".") or parsed.hostname.lower() != parsed.hostname):
            raise ValueError("invalid URL")
        return "https://" + parsed.hostname + (":7777" if port == 7777 else "")
    except (ValueError, TypeError) as exc:
        raise IdentityUnavailable("OIDC endpoint configuration invalid") from exc


def _config() -> _Config:
    env = os.environ
    issuer = env.get("AIOPS_PORTAL_OIDC_ISSUER", "")
    authorize = env.get("AIOPS_PORTAL_OIDC_AUTHORIZATION_ENDPOINT", "")
    token = env.get("AIOPS_PORTAL_OIDC_TOKEN_ENDPOINT", "")
    client = env.get("AIOPS_PORTAL_OIDC_CLIENT_ID", "")
    redirect = env.get("AIOPS_PORTAL_OIDC_REDIRECT_URI", "")
    origin = _origin(issuer)
    if (not issuer.startswith(origin + "/") or issuer.endswith("/")
            or _origin(authorize) != origin or _origin(token) != origin
            or not urllib.parse.urlsplit(authorize).path.startswith("/")
            or not urllib.parse.urlsplit(token).path.startswith("/")
            or _origin(redirect, portal_redirect=True) == origin
            or urllib.parse.urlsplit(redirect).path != "/auth/oidc/callback"
            or not re.fullmatch(r"[A-Za-z0-9._~-]{3,128}", client)
            or env.get("AIOPS_PORTAL_OIDC_AUDIENCE") != client
            or authorize == token):
        raise IdentityUnavailable("OIDC endpoint configuration invalid")
    return _Config(issuer, authorize, token, client, redirect,
                   _origin(redirect, portal_redirect=True))


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _cleanup(now: int) -> None:
    for key, value in list(_pending.items()):
        if value.expires <= now:
            _pending.pop(key, None)
    for key, value in list(_sessions.items()):
        if value.expires <= now:
            _sessions.pop(key, None)


def _unknown(status: int, reason: str) -> JSONResponse:
    return JSONResponse(
        {"state": "UNKNOWN", "reason": reason, "connection_state": "UNKNOWN",
         "tenant_acl_qualified": False},
        status_code=status, headers={"Cache-Control": "no-store"},
    )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _exchange(config: _Config, code: str, verifier: str) -> str:
    """Pinned issuer endpoint, no ambient proxies/redirects or browser token."""
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code", "code": code,
        "client_id": config.client, "redirect_uri": config.redirect,
        "code_verifier": verifier,
    }).encode("ascii")
    request = urllib.request.Request(
        config.token, data=data, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json"},
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirect(),
    )
    try:
        with opener.open(request, timeout=5) as response:
            if response.status != 200:
                raise IdentityUnavailable("OIDC token endpoint unavailable")
            raw = response.read(65537)
        if len(raw) > 65536:
            raise IdentityUnavailable("OIDC token response too large")
        payload = _json_strict(raw)
        value = payload.get("id_token") if isinstance(payload, dict) else None
        if not isinstance(value, str):
            raise IdentityUnavailable("OIDC ID token missing")
        return value
    except (urllib.error.URLError, OSError, ValueError, UnicodeError) as exc:
        raise IdentityUnavailable("OIDC token endpoint unavailable") from exc


@router.get("/auth/oidc/login")
def oidc_login():
    try:
        config = _config()
    except IdentityUnavailable:
        return _unknown(503, "OIDC_UNAVAILABLE")
    state, nonce, verifier = (_b64(secrets.token_bytes(32)) for _ in range(3))
    now = int(time.time())
    with _lock:
        _cleanup(now)
        if len(_pending) >= _MAX_PENDING:
            return _unknown(503, "OIDC_UNAVAILABLE")
        _pending[_digest(state)] = _Pending(verifier, nonce, now + _STATE_TTL)
    challenge = _b64(hashlib.sha256(verifier.encode("ascii")).digest())
    query = urllib.parse.urlencode({
        "response_type": "code", "client_id": config.client,
        "redirect_uri": config.redirect, "scope": "openid",
        "state": state, "nonce": nonce, "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    response = RedirectResponse(config.authorize + "?" + query, status_code=303)
    response.set_cookie(_STATE_COOKIE, state, max_age=_STATE_TTL, path="/",
                        secure=True, httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return response


def _unambiguous_state_cookie(request: Request) -> str:
    """Reject duplicate/split OIDC state cookies before any IdP exchange.

    Starlette collapses same-name cookies, so a browser or intermediary must
    not select which CSRF state is used. This does not authenticate an actor.
    """
    raw_fields = request.headers.getlist("cookie")
    if len(raw_fields) != 1:
        return ""
    pattern = r"(?:^|;)\\s*" + re.escape(_STATE_COOKIE) + r"\\s*="
    if len(re.findall(pattern, raw_fields[0])) != 1:
        return ""
    return request.cookies.get(_STATE_COOKIE, "")


@router.get("/auth/oidc/callback")
def oidc_callback(request: Request, code: str = "", state: str = "",
                  error: str = ""):
    # No request body/header or browser bearer can inject actor/tenant.
    cookie = _unambiguous_state_cookie(request)
    if (error or not _OPAQUE.fullmatch(state) or not _OPAQUE.fullmatch(cookie)
            or not hmac.compare_digest(state, cookie)
            or _CODE.fullmatch(code) is None):
        return _unknown(401, "OIDC_CALLBACK_REJECTED")
    # Cookie security is not port-scoped: a second HTTPS listener on the
    # same hostname must not consume the configured :7777 callback state.
    # This validates the ASGI request shape, not actual Debian TLS/PortBindings.
    try:
        config = _config()
    except IdentityUnavailable:
        return _unknown(503, "OIDC_UNAVAILABLE")
    expected = urllib.parse.urlsplit(config.redirect)
    if (request.url.scheme != "https"
            or request.headers.get("host", "").lower() != expected.netloc.lower()
            or request.url.path != "/auth/oidc/callback"):
        return _unknown(401, "OIDC_CALLBACK_REJECTED")
    now = int(time.time())
    with _lock:
        _cleanup(now)
        pending = _pending.pop(_digest(state), None)
    if pending is None or pending.expires <= now:
        return _unknown(401, "OIDC_CALLBACK_REJECTED")
    try:
        id_token = _exchange(config, code, pending.verifier)
        actor = verify_server_oidc_assertion(id_token, now=now,
                                             expected_nonce=pending.nonce)
        if actor.issuer != config.issuer or actor.audience != config.client:
            raise IdentityRejected("OIDC issuer/audience mismatch")
    except IdentityRejected:
        return _unknown(401, "OIDC_CALLBACK_REJECTED")
    except IdentityUnavailable:
        return _unknown(503, "OIDC_UNAVAILABLE")
    ttl = min(_SESSION_TTL, actor.expires_at - now)
    if ttl <= 0:
        return _unknown(401, "OIDC_CALLBACK_REJECTED")
    handle = _b64(secrets.token_bytes(32))
    with _lock:
        _cleanup(now)
        if len(_sessions) >= _MAX_SESSIONS:
            return _unknown(503, "OIDC_UNAVAILABLE")
        _sessions[_digest(handle)] = _Session(actor, now + ttl)
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(_STATE_COOKIE, path="/", secure=True,
                           httponly=True, samesite="lax")
    response.set_cookie(_SESSION_COOKIE, handle, max_age=ttl, path="/",
                        secure=True, httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return response


def _session_from_cookie(request: Request) -> _Session | None:
    # Reject cookie-tossing ambiguity before Starlette collapses duplicate
    # names (last value wins). Neither a valid nor a forged duplicate may
    # choose which server-owned OIDC handle is authenticated.
    cookie_pattern = r"(?:^|;)\s*" + re.escape(_SESSION_COOKIE) + r"\s*="
    headers = request.headers.getlist("cookie")
    occurrences = sum(len(re.findall(cookie_pattern, header))
                      for header in headers)
    # Multiple Cookie fields are ambiguous across ASGI/framework parsers.
    # Reject them even if just one contains the OIDC handle.
    if len(headers) != 1 or occurrences != 1:
        return None
    value = request.cookies.get(_SESSION_COOKIE, "")
    if not _OPAQUE.fullmatch(value):
        return None
    now = int(time.time())
    with _lock:
        _cleanup(now)
        session = _sessions.get(_digest(value))
        return session if session is not None and session.expires > now else None


@router.get("/api/portal/session")
def oidc_session_status(request: Request):
    if _session_from_cookie(request) is None:
        return _unknown(401, "OIDC_SESSION_REQUIRED")
    # Session proves identity only. No Core ACL, no business identifiers.
    return _unknown(503, "TENANT_ACL_NOT_QUALIFIED")


@router.post("/auth/oidc/logout")
def oidc_logout(request: Request):
    try:
        origin = _config().origin
    except IdentityUnavailable:
        return _unknown(503, "OIDC_UNAVAILABLE")
    if not hmac.compare_digest(request.headers.get("origin", ""), origin):
        return _unknown(403, "OIDC_CSRF_REJECTED")
    value = request.cookies.get(_SESSION_COOKIE, "")
    if _OPAQUE.fullmatch(value):
        with _lock:
            _sessions.pop(_digest(value), None)
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(_SESSION_COOKIE, path="/", secure=True,
                           httponly=True, samesite="lax")
    return response
