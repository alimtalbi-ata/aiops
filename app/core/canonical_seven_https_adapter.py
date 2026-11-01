"""Core-owned HTTPS source dispatch contract for synthetic seven-event PG16 readback.

Transport binding is supplied by a *trusted* TLS listener, not a request header.
The adapter authenticates its own service credential before inspecting scope,
reads through Core's SQL producer and emits only a source proof or UNKNOWN.
It never authorizes a human, issues a portable signature, or writes to GLPI.
"""
from __future__ import annotations

import base64
import hmac
import json
from datetime import datetime

from core import actor_canonical_seven_source as binding
from core.canonical_seven_pg_source import read_canonical_seven

PATH = "/v2/canonical-seven-readback"
MAX_BODY = 8192
UNKNOWN = {"decision": "UNKNOWN"}


def dispatch_canonical_seven(*, method: str, path: str, tls: bool,
                             authorization: str, body: bytes,
                             client_id: str, client_secret: str,
                             connect, source: str, source_issuer: str,
                             now: datetime) -> tuple[int, dict]:
    """Return HTTP status and JSON for a trusted HTTPS listener.

    The listener must enforce server TLS and must pass its verified transport
    state, not X-Forwarded-Proto. The caller pins credentials, SQL connection,
    source and source_issuer outside the request. The actor's IdP issuer is
    independently checked against the synthetic PG grant, never equated with
    the trusted Core source issuer. Any failure is negative-only.
    """
    if tls is not True:
        return 503, dict(UNKNOWN)
    if method != "POST" or path != PATH:
        return 404, dict(UNKNOWN)
    if (type(client_id) is not str or not client_id
            or type(client_secret) is not str or len(client_secret) < 32
            or type(authorization) is not str or len(authorization) > 512):
        return 503, dict(UNKNOWN)
    expected = "Basic " + base64.b64encode(
        (client_id + ":" + client_secret).encode("utf-8")).decode("ascii")
    if not hmac.compare_digest(authorization, expected):
        return 401, dict(UNKNOWN)
    if not isinstance(body, bytes) or not 1 <= len(body) <= MAX_BODY:
        return 404, dict(UNKNOWN)
    try:
        request = json.loads(body.decode("utf-8"))
        if (not isinstance(request, dict)
                or set(request) != set(binding._SCOPE)
                or any(type(v) is not str or not v for v in request.values())
                or request["permission"] != "run:read"):
            return 404, dict(UNKNOWN)
        with connect() as conn:
            proof = read_canonical_seven(
                conn, request, source=source, issuer=source_issuer, now=now)
        if proof is None:
            return 404, dict(UNKNOWN)
        return 200, proof
    except Exception:
        # SQL failures, missing authority or malformed JSON never enumerate.
        return 503, dict(UNKNOWN)
