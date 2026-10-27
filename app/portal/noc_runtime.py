"""Authenticated, read-only bridge for a signed NOC read-model envelope.

This adapter contacts only an operator-allowlisted origin. It never writes to
Checkmk/Thruk or any AIOps backend, follows no redirects, verifies a bounded
HMAC-signed response, and deliberately does not attest application screenshots
or authorize remediation.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()
SCHEMA = "aiops.noc-runtime-readmodel.v1"
OUTPUT_SCHEMA = "aiops.noc-runtime-envelope.v1"
TIMEOUT_SECONDS = 3
MAX_RESPONSE_BYTES = 256 * 1024
MAX_AGE_SECONDS = 300
VALID_STATES = {"OK", "WARN", "CRIT", "UNKNOWN"}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,95}\Z")
TICKET_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
BEARER_TOKEN = re.compile(r"[A-Za-z0-9._~+/-]+=*\Z")
UTC_TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z"
)


class NocSourceNotConfigured(ValueError):
    """Raised when the optional upstream contract is not fully configured."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_json_constant(value: str):
    raise ValueError("non-standard JSON constant")


def _canonical_origin(value: str, *, endpoint: bool) -> tuple[str, urllib.parse.SplitResult]:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError("invalid NOC origin")
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.netloc != parsed.netloc.lower()
    ):
        raise ValueError("invalid NOC origin")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("invalid NOC origin") from exc
    if endpoint:
        if not parsed.path.startswith("/") or parsed.path == "/" or "\\" in parsed.path:
            raise ValueError("NOC endpoint path is required")
    elif parsed.path not in ("", "/"):
        raise ValueError("allowed origins must not include a path")
    origin = parsed.scheme.lower() + "://" + parsed.netloc
    return origin, parsed


def _configuration() -> tuple[str, str, bytes, str]:
    url = os.getenv("AIOPS_NOC_READ_MODEL_URL", "")
    token = os.getenv("AIOPS_NOC_READ_MODEL_TOKEN", "")
    hmac_key = os.getenv("AIOPS_NOC_READ_MODEL_HMAC_KEY", "")
    allowed_text = os.getenv("AIOPS_NOC_ALLOWED_ORIGINS", "")
    if not url or not token or not hmac_key or not allowed_text:
        raise NocSourceNotConfigured("NOC source not configured")
    origin, _ = _canonical_origin(url, endpoint=True)
    allowed = set()
    for entry in allowed_text.split(","):
        entry = entry.strip()
        if not entry:
            continue
        allowed_origin, _ = _canonical_origin(entry, endpoint=False)
        allowed.add(allowed_origin)
    if not allowed or origin not in allowed:
        raise ValueError("NOC origin is not allowlisted")
    if (
        len(token) < 16
        or BEARER_TOKEN.fullmatch(token) is None
        or len(hmac_key.encode("utf-8")) < 32
        or "\r" in hmac_key
        or "\n" in hmac_key
    ):
        raise ValueError("NOC credentials do not meet minimum length or format")
    return url, token, hmac_key.encode("utf-8"), origin


def _parse_utc(value: object, label: str) -> datetime:
    if not isinstance(value, str) or UTC_TIMESTAMP.fullmatch(value) is None:
        raise ValueError("invalid UTC timestamp: " + label)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("invalid UTC timestamp: " + label) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("invalid UTC timestamp: " + label)
    return parsed.astimezone(timezone.utc)


def _project_signed_payload(
    raw: bytes, *, digest_header: str | None, signature_header: str | None,
    hmac_key: bytes, source_origin: str, now: datetime | None = None,
) -> dict:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("invalid NOC response size")
    digest = hashlib.sha256(raw).hexdigest()
    if not isinstance(digest_header, str) or not hmac.compare_digest(
        digest, digest_header.lower()
    ):
        raise ValueError("NOC payload digest mismatch")
    expected_signature = hmac.new(hmac_key, raw, hashlib.sha256).hexdigest()
    if (
        not isinstance(signature_header, str)
        or SHA256.fullmatch(signature_header.lower()) is None
        or not hmac.compare_digest(expected_signature, signature_header.lower())
    ):
        raise ValueError("NOC payload signature mismatch")
    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("invalid signed NOC JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError("invalid NOC schema")
    if payload.get("provenance") != "RUNTIME_READMODEL":
        raise ValueError("invalid NOC provenance")
    if payload.get("live_remediation_authorized", False) is not False:
        raise ValueError("NOC source attempted to authorize remediation")
    if payload.get("evidence_runtime_attested", False) is not False:
        raise ValueError("NOC source attempted to attest evidence bytes")
    if payload.get("production_qualified", False) is not False:
        raise ValueError("NOC source attempted to claim production qualification")
    run_id = payload.get("run_id")
    incident_id = payload.get("incident_id")
    if not isinstance(run_id, str) or IDENTIFIER.fullmatch(run_id) is None:
        raise ValueError("invalid NOC run identity")
    if not isinstance(incident_id, str) or IDENTIFIER.fullmatch(incident_id) is None:
        raise ValueError("invalid NOC incident identity")
    if any(key in payload for key in (
        "handoff_02_03", "handoff_identity_sha256", "handoff_status",
        "handoff_runtime_authenticated",
    )):
        # This portal image does not yet embed the canonical 02->03 verifier.
        # Do not accept a provider's self-asserted handoff result.
        raise ValueError("NOC handoff verifier is not integrated")
    observed = _parse_utc(payload.get("observed_at"), "observed_at")
    clock = now or datetime.now(timezone.utc)
    age = (clock.astimezone(timezone.utc) - observed).total_seconds()
    if age < 0 or age > MAX_AGE_SECONDS:
        raise ValueError("stale or future NOC observation")
    event_timestamp = payload.get("event_timestamp_utc")
    if event_timestamp is not None:
        event_time = _parse_utc(event_timestamp, "event_timestamp_utc")
        if event_time > clock.astimezone(timezone.utc):
            raise ValueError("future NOC event timestamp")
    ticket_id = payload.get("ticket_id")
    if ticket_id is not None and (
        not isinstance(ticket_id, str) or TICKET_ID.fullmatch(ticket_id) is None
    ):
        raise ValueError("invalid NOC ticket identifier")
    correlation_id = payload.get("correlation_id")
    if correlation_id is not None and (
        not isinstance(correlation_id, str) or IDENTIFIER.fullmatch(correlation_id) is None
    ):
        raise ValueError("invalid NOC correlation identifier")
    evidence_sha256 = payload.get("evidence_sha256")
    if evidence_sha256 is not None and (
        not isinstance(evidence_sha256, str) or SHA256.fullmatch(evidence_sha256) is None
    ):
        raise ValueError("invalid NOC evidence digest")
    steps = payload.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 100:
        raise ValueError("invalid NOC timeline")
    projected_steps = []
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("invalid NOC timeline step")
        name, state = step.get("name"), step.get("state")
        if not isinstance(name, str) or not name.strip() or len(name) > 128:
            raise ValueError("invalid NOC timeline step")
        if not isinstance(state, str) or state not in VALID_STATES:
            raise ValueError("invalid NOC timeline step")
        projected_steps.append({"name": name, "state": state})
    # The HMAC authenticates these bytes as coming from the configured key
    # holder. It does not attest a UI capture, external ticket, or live action.
    return {
        "schema": OUTPUT_SCHEMA,
        "source_mode": "ALLOWLISTED_HMAC_SIGNED_READ_MODEL",
        "source_origin": source_origin,
        "source_payload_sha256": digest,
        "source_payload_authenticated": True,
        "source_authentication": "HMAC_SHA256_VERIFIED",
        "provenance": "AUTHENTICATED_SOURCE_PAYLOAD_NOT_RUNTIME_ATTESTATION",
        "runtime_attested": False,
        "runtime_authenticated": False,
        "run_id": run_id,
        "incident_id": incident_id,
        "correlation_id": correlation_id,
        "handoff_status": "ABSENT",
        "handoff_runtime_authenticated": False,
        "ticket_id": ticket_id,
        "ticket_provenance": "UPSTREAM_SIGNED_CLAIM" if ticket_id else "ABSENT",
        "event_timestamp_utc": event_timestamp,
        "event_timestamp_provenance": "UPSTREAM_SIGNED_CLAIM" if event_timestamp else "ABSENT",
        "observed_at_utc": observed.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "evidence_sha256": evidence_sha256,
        "evidence_status": "DIGEST_REPORTED_NOT_BYTES_VERIFIED" if evidence_sha256 else "ABSENT",
        "evidence_runtime_attested": False,
        "steps": projected_steps,
        "live_remediation_authorized": False,
        "production_qualified": False,
    }


def read_signed_noc_snapshot() -> dict:
    url, token, hmac_key, origin = _configuration()
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer " + token,
            "User-Agent": "AIOps-Portal-NOC-ReadOnly/1",
        },
        method="GET",
    )
    # Do not inherit ambient HTTP_PROXY/HTTPS_PROXY settings: credentials must
    # never be sent through an unreviewed proxy configured outside this contract.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
        if response.geturl() != url:
            raise ValueError("NOC redirect refused")
        if response.getcode() != 200:
            raise ValueError("NOC upstream status rejected")
        headers = response.headers
        content_type = headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ValueError("NOC upstream content type rejected")
        length = headers.get("Content-Length")
        if length is not None:
            if not length.isdigit() or int(length) > MAX_RESPONSE_BYTES:
                raise ValueError("NOC upstream body too large")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if length is not None and len(raw) != int(length):
            raise ValueError("NOC upstream body length mismatch")
    return _project_signed_payload(
        raw,
        digest_header=headers.get("X-AIOps-Read-Model-SHA256"),
        signature_header=headers.get("X-AIOps-Read-Model-Signature"),
        hmac_key=hmac_key,
        source_origin=origin,
    )


def _require_portal_read_auth(authorization: str | None) -> None:
    expected = os.getenv("AIOPS_PORTAL_READ_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503, detail="portal_read_auth_not_configured")
    scheme, separator, supplied = (authorization or "").partition(" ")
    if (
        not separator
        or scheme.lower() != "bearer"
        or not supplied
        or not hmac.compare_digest(supplied, expected)
    ):
        raise HTTPException(status_code=401, detail="invalid_portal_read_token")


def _noc_json_response(content: dict, *, status_code: int = 200) -> JSONResponse:
    """Apply non-cacheable security headers to success and every error path."""
    return JSONResponse(
        content=content,
        status_code=status_code,
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.get("/api/noc/runtime-state", name="authenticated_noc_runtime_read_model")
def noc_runtime_state(authorization: str | None = Header(default=None)):
    """Return a signed, bounded NOC projection through the existing portal only."""
    try:
        _require_portal_read_auth(authorization)
    except HTTPException as exc:
        # Authentication/configuration failures must not be cached by browsers
        # or intermediary proxies, and must not reach the upstream.
        return _noc_json_response({"detail": exc.detail}, status_code=exc.status_code)
    try:
        payload = read_signed_noc_snapshot()
    except NocSourceNotConfigured:
        return _noc_json_response(
            {"detail": "noc_source_not_configured"}, status_code=503
        )
    except Exception:
        # Do not leak URLs, upstream bodies, credentials, or parser exceptions.
        return _noc_json_response(
            {"detail": "noc_source_unavailable_or_unverified"}, status_code=503
        )
    return _noc_json_response(payload)
