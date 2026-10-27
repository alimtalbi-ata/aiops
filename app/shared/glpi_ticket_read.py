"""Read-only GLPI Ticket observation; no incident/Run correlation or LIVE authority.

Intended for a future adapter inside the aiops2-integration network, NOT for
direct calls from the public Portal. Never creates sessions or writes tickets.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

SCHEMA = "aiops.glpi.ticket-observation.v1"
MAX_RESPONSE_BYTES = 64 * 1024
TIMEOUT_SECONDS = 3
_TOKEN = re.compile(r"[A-Za-z0-9._~+/-]{16,512}\Z")
_MODIFIED = re.compile(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\Z")


class GLPIUnverified(ValueError):
    """Configuration, upstream, identity or provenance cannot be trusted."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _strict_json_pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str):
    raise ValueError("non-standard JSON constant")


def _integer(value: object, *, zero_allowed: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise GLPIUnverified("invalid GLPI identifier")
    if isinstance(value, str) and (not value.isascii() or not value.isdecimal() or len(value) > 10):
        raise GLPIUnverified("invalid GLPI identifier")
    number = int(value)
    if not (0 if zero_allowed else 1) <= number <= 2147483647:
        raise GLPIUnverified("invalid GLPI identifier")
    return number


def _configuration(env: dict | None = None) -> tuple[str, str, str, int]:
    env = os.environ if env is None else env
    base = env.get("AIOPS_GLPI_API_BASE_URL", "")
    parsed = urllib.parse.urlsplit(base)
    if (
        not base or base.strip() != base or parsed.scheme not in ("http", "https")
        or not parsed.hostname or parsed.username is not None or parsed.password is not None
        or parsed.query or parsed.fragment or parsed.path != "/apirest.php"
        or "\\" in base or parsed.netloc != parsed.netloc.lower()
    ):
        raise GLPIUnverified("invalid GLPI API base URL")
    try:
        parsed.port
    except ValueError as exc:
        raise GLPIUnverified("invalid GLPI port") from exc
    # Plain HTTP is only acceptable for the isolated real GLPI CI container.
    if parsed.scheme == "http" and not (
        env.get("CI") == "true" and parsed.hostname == "aiops2-glpi"
    ):
        raise GLPIUnverified("GLPI requires HTTPS outside isolated CI")
    app_token = env.get("AIOPS_GLPI_APP_TOKEN", "")
    session_token = env.get("AIOPS_GLPI_SESSION_TOKEN", "")
    if (
        not isinstance(app_token, str) or _TOKEN.fullmatch(app_token) is None
        or not isinstance(session_token, str) or _TOKEN.fullmatch(session_token) is None
    ):
        raise GLPIUnverified("GLPI API tokens missing or invalid")
    entity = _integer(env.get("AIOPS_GLPI_ENTITY_ID"), zero_allowed=True)
    return base, app_token, session_token, entity


def _project(raw: bytes, *, requested_id: int, expected_entity: int,
             source: str, now: datetime | None = None) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_RESPONSE_BYTES:
        raise GLPIUnverified("invalid GLPI response size")
    try:
        ticket = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_json_pairs,
                            parse_constant=_reject_constant)
    except (UnicodeError, ValueError) as exc:
        raise GLPIUnverified("invalid GLPI response JSON") from exc
    if not isinstance(ticket, dict):
        raise GLPIUnverified("invalid GLPI ticket object")
    ticket_id = _integer(ticket.get("id"))
    entity_id = _integer(ticket.get("entities_id"), zero_allowed=True)
    status = ticket.get("status")
    if (
        ticket_id != requested_id or entity_id != expected_entity
        or type(status) is not int or not 1 <= status <= 6
    ):
        raise GLPIUnverified("GLPI ticket identity/entity/status mismatch")
    modified = ticket.get("date_mod")
    if modified is not None and (
        not isinstance(modified, str) or _MODIFIED.fullmatch(modified) is None
    ):
        raise GLPIUnverified("invalid GLPI modification timestamp")
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise GLPIUnverified("observation clock must be timezone-aware")
    return {
        "schema": SCHEMA,
        "state": "OBSERVED_UNCORRELATED",
        "ticket_id": str(ticket_id),
        "ticket_id_provenance": "GLPI_API_RESPONSE_MATCHED_REQUEST",
        "entity_id": entity_id,
        "status_code": status,
        "source": "AUTHENTICATED_GLPI_API_READ_NOT_ATTESTATION",
        "source_origin": source,
        "response_sha256": hashlib.sha256(raw).hexdigest(),
        "read_at_utc": clock.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "modified_at_glpi_local_unqualified": modified,
        "incident_id": None,
        "run_id": None,
        "correlation_state": "UNKNOWN",
        "runtime_attested": False,
        "production_qualified": False,
        "live_remediation_authorized": False,
    }


def read_ticket(ticket_id: object, *, env: dict | None = None,
                transport=None, now: datetime | None = None) -> dict:
    """GET a single numeric ticket through an explicit, bounded GLPI API origin.

    transport(request, timeout=...) is injectable for offline unit tests only.
    Production transport disables proxies and redirects. No API initSession or
    ticket writes; the session token must already be provisioned securely.
    """
    number = _integer(ticket_id)  # validate untrusted identity BEFORE network
    base, app_token, session_token, entity = _configuration(env)
    url = base + "/Ticket/" + str(number)
    req = urllib.request.Request(
        url, method="GET", headers={
            "Accept": "application/json",
            "App-Token": app_token,
            "Session-Token": session_token,
            "User-Agent": "AIOps-GLPI-ReadOnly/1",
        },
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirect()
    )
    try:
        response_ctx = (
            transport(req, timeout=TIMEOUT_SECONDS) if transport is not None
            else opener.open(req, timeout=TIMEOUT_SECONDS)
        )
        with response_ctx as response:
            if response.geturl() != url or response.getcode() != 200:
                raise GLPIUnverified("GLPI redirect or unexpected status")
            ctype = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if ctype != "application/json":
                raise GLPIUnverified("GLPI response content type mismatch")
            length = response.headers.get("Content-Length")
            if length is not None and (
                not length.isascii() or not length.isdecimal()
                or int(length) > MAX_RESPONSE_BYTES
            ):
                raise GLPIUnverified("invalid GLPI Content-Length")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if length is not None and len(raw) != int(length):
                raise GLPIUnverified("GLPI Content-Length mismatch")
        return _project(
            raw, requested_id=number, expected_entity=entity,
            source=urllib.parse.urlsplit(base).scheme + "://" + urllib.parse.urlsplit(base).netloc,
            now=now,
        )
    except GLPIUnverified:
        raise
    except (OSError, ValueError, TypeError) as exc:
        # Do not expose upstream errors or credentials in HTTP responses/logs.
        raise GLPIUnverified("GLPI read failed or unverified") from exc
