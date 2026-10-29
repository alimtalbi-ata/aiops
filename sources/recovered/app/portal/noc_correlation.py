"""Read-only, fail-closed join of signed NOC identity to canonical Core Run.

No source identity, signed digest or model output is runtime attestation.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from fastapi import APIRouter, Header, HTTPException
from portal import noc_runtime

router = APIRouter()
SCHEMA = "aiops.noc-canonical-correlation.v1"
MAX_CORE_BYTES = 32 * 1024


def _read_core_run(run_id: str) -> dict:
    """GET only the exact canonical Run from the fixed internal Core origin."""
    if not isinstance(run_id, str) or noc_runtime.IDENTIFIER.fullmatch(run_id) is None:
        raise ValueError("invalid canonical run identifier")
    base = os.getenv("CORE_URL", "http://aiops2-core:810").rstrip("/")
    parsed = urllib.parse.urlsplit(base)
    if (parsed.scheme != "http" or parsed.hostname not in
            ("aiops2-core", "localhost", "127.0.0.1") or
            parsed.username is not None or parsed.password is not None or
            parsed.path or parsed.query or parsed.fragment or parsed.port != 810):
        raise ValueError("unapproved Core endpoint")
    url = base + "/api/noc/runs/" + run_id
    internal_token = os.getenv("AIOPS_INTERNAL_TOKEN", "")
    if (not isinstance(internal_token, str) or len(internal_token) < 32
            or len(internal_token) > 256 or not internal_token.isascii()
            or any(char.isspace() for char in internal_token)):
        raise ValueError("Core NOC internal credential not configured")
    request = urllib.request.Request(url, headers={"Accept": "application/json",
                                                  "Authorization": "Bearer " + internal_token}, method="GET")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), noc_runtime._NoRedirect())
    with opener.open(request, timeout=3) as response:
        if response.geturl() != url or response.getcode() != 200:
            raise ValueError("Core read rejected")
        if response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise ValueError("Core response is not JSON")
        raw = response.read(MAX_CORE_BYTES + 1)
    if not raw or len(raw) > MAX_CORE_BYTES:
        raise ValueError("invalid Core response size")
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=noc_runtime._reject_duplicate_keys,
                      parse_constant=noc_runtime._reject_json_constant)
    if not isinstance(data, dict) or not isinstance(data.get("run"), dict):
        raise ValueError("invalid canonical Run response")
    return data["run"]


def correlate(noc: dict, run: dict) -> dict:
    """Project only exact, independently readable canonical identity; never infer LIVE."""
    if (not isinstance(noc, dict) or noc.get("schema") != noc_runtime.OUTPUT_SCHEMA or
            noc.get("source_payload_authenticated") is not True or
            noc.get("source_authentication") != "HMAC_SHA256_VERIFIED" or
            noc.get("runtime_authenticated") is not False or
            noc.get("live_remediation_authorized") is not False):
        raise ValueError("unverified NOC projection")
    if not isinstance(run, dict):
        raise ValueError("invalid Core Run")
    run_id, incident_id = run.get("run_id"), run.get("incident_id")
    if (not isinstance(run_id, str) or noc_runtime.IDENTIFIER.fullmatch(run_id) is None or
            not isinstance(incident_id, str) or noc_runtime.IDENTIFIER.fullmatch(incident_id) is None or
            not isinstance(run.get("status"), str) or not run["status"] or
            run.get("mode") not in ("DEMO", "REPLAY", "STORY", "LIVE")):
        raise ValueError("invalid canonical Run identity")
    # A signed source is not a tenant authorization decision. Reuse the
    # conservative recursive scope fence already enforced at NOC ingestion:
    # Core may introduce nested or aliased tenant claims independently.
    noc_runtime._reject_unqualified_tenant_scope(noc)
    noc_runtime._reject_unqualified_tenant_scope(run)
    if run["mode"] == "LIVE":
        raise ValueError("LIVE correlation requires independently qualified authorization")
    matched = run_id == noc.get("run_id") and incident_id == noc.get("incident_id")
    return {
        "schema": SCHEMA,
        "state": "MATCHED_UNATTESTED" if matched else "UNKNOWN",
        "reason": "CANONICAL_IDENTITIES_MATCH" if matched else "IDENTITY_MISMATCH",
        "source": "SIGNED_NOC_PAYLOAD_NOT_RUNTIME_ATTESTATION",
        "noc_source_origin": noc.get("source_origin"),
        "noc_payload_sha256": noc.get("source_payload_sha256"),
        "noc_run_id": noc.get("run_id"),
        "noc_incident_id": noc.get("incident_id"),
        "canonical_run_id": run_id if matched else None,
        "canonical_incident_id": incident_id if matched else None,
        "canonical_mode": run["mode"] if matched else None,
        "canonical_status": run["status"] if matched else None,
        "data_classification": "SYNTHETIC_CANONICAL_RUN" if matched else "UNKNOWN",
        "grafana_observation": "NOT_TESTED",
        "rag_diagnostic": "NOT_TESTED",
        "runtime_authenticated": False,
        "production_qualified": False,
        "live_remediation_authorized": False,
    }


@router.get("/api/noc/correlation", name="authenticated_noc_canonical_correlation")
def noc_correlation(authorization: str | None = Header(default=None)):
    try:
        noc_runtime._require_portal_read_auth(authorization)
    except HTTPException as exc:
        return noc_runtime._noc_json_response({"detail": exc.detail}, status_code=exc.status_code)
    try:
        noc = noc_runtime.read_signed_noc_snapshot()
    except noc_runtime.NocSourceNotConfigured:
        return noc_runtime._noc_json_response({"detail": "noc_source_not_configured"}, status_code=503)
    except Exception:
        return noc_runtime._noc_json_response({"detail": "noc_source_unavailable_or_unverified"}, status_code=503)
    try:
        run = _read_core_run(noc["run_id"])
        result = correlate(noc, run)
    except Exception:
        return noc_runtime._noc_json_response({"detail": "canonical_correlation_unavailable_or_unverified"}, status_code=503)
    return noc_runtime._noc_json_response(result)
