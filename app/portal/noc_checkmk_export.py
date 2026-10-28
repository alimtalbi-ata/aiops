"""Offline Checkmk/Livestatus export preview, selectively adapted from PR #36.

Operator-submitted exports are never treated as observed, authenticated or tenant
authorized. No monitoring network call, persistence or remediation is performed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from portal import noc_runtime

router = APIRouter()
SCHEMA = "aiops-checkmk-host-export-v1"
OUTPUT_SCHEMA = "aiops.noc-checkmk-offline-preview.v1"
MAX_BODY_BYTES = 64 * 1024
MAX_HOSTS = 500
MAX_AGE_SECONDS = 300
STATES = {0: "OK", 1: "WARN", 2: "CRIT", 3: "UNKNOWN"}


def preview_export(payload: object, *, now: datetime | None = None) -> dict:
    """Validate PR36's offline export shape and return only aggregate counts."""
    if not isinstance(payload, dict) or set(payload) != {
        "schema", "source", "read_only", "live_remediation_authorized",
        "captured_at", "hosts",
    }:
        raise ValueError("unreviewed Checkmk export fields")
    if (payload["schema"] != SCHEMA or payload["source"] != "CHECKMK_EXPORT"
            or payload["read_only"] is not True
            or payload["live_remediation_authorized"] is not False):
        raise ValueError("untrusted Checkmk export")
    captured = noc_runtime._parse_utc(payload["captured_at"], "captured_at")
    clock = now or datetime.now(timezone.utc)
    age = (clock.astimezone(timezone.utc) - captured).total_seconds()
    if age < 0 or age > MAX_AGE_SECONDS:
        raise ValueError("stale or future Checkmk export")
    hosts = payload["hosts"]
    if not isinstance(hosts, list) or not 1 <= len(hosts) <= MAX_HOSTS:
        raise ValueError("invalid host count")
    counts = {label: 0 for label in STATES.values()}
    seen: set[str] = set()
    for row in hosts:
        # Strict columns: reject tenant/org/workspace claims and hidden commands.
        if not isinstance(row, dict) or set(row) != {"name", "state", "output"}:
            raise ValueError("unreviewed Checkmk host columns")
        name, state, output = row["name"], row["state"], row["output"]
        if (not isinstance(name, str)
                or noc_runtime.IDENTIFIER.fullmatch(name) is None
                or name in seen or type(state) is not int or state not in STATES
                or not isinstance(output, str) or len(output) > 1000):
            raise ValueError("invalid Checkmk host")
        seen.add(name)
        counts[STATES[state]] += 1
    # Deliberately omit host names, plugin output, tenant IDs and raw export.
    return {
        "schema": OUTPUT_SCHEMA,
        "state": "UNVERIFIED_OFFLINE_EXPORT",
        "provenance": "OPERATOR_EXPORT_UNVERIFIED",
        "transport": "OFFLINE_LIVESTATUS_EXPORT",
        "host_count": len(hosts),
        "state_counts": counts,
        "claimed_capture_age_seconds": age,
        "source_runtime_observed": False,
        "runtime_authenticated": False,
        "tenant_acl_qualified": False,
        "grafana_observation": "NOT_TESTED",
        "llm_inference_performed": False,
        "live_remediation_authorized": False,
        "production_qualified": False,
    }


@router.post("/api/noc/checkmk-export/preview", name="noc_offline_checkmk_preview")
async def noc_checkmk_export_preview(
    request: Request, authorization: str | None = Header(default=None),
):
    try:
        noc_runtime._require_portal_read_auth(authorization)
    except HTTPException as exc:
        return noc_runtime._noc_json_response({"detail": exc.detail}, status_code=exc.status_code)
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        return noc_runtime._noc_json_response({"detail": "json_required"}, status_code=415)
    length = request.headers.get("content-length")
    if length is not None and (not length.isdigit() or int(length) > MAX_BODY_BYTES):
        return noc_runtime._noc_json_response({"detail": "export_too_large"}, status_code=413)
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_BODY_BYTES:
            return noc_runtime._noc_json_response({"detail": "export_too_large"}, status_code=413)
    try:
        payload = json.loads(bytes(raw).decode("utf-8"),
                             object_pairs_hook=noc_runtime._reject_duplicate_keys,
                             parse_constant=noc_runtime._reject_json_constant)
        result = preview_export(payload)
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        return noc_runtime._noc_json_response({"detail": "export_invalid_or_unverified"}, status_code=400)
    return noc_runtime._noc_json_response(result)
