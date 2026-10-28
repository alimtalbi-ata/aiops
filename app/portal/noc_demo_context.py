"""DEMO-only, read-only join: signed NOC event → Core Run → synthetic RAG citation.

This is a source-identity join, not observed monitoring, tenant RBAC, LLM
inference or evidence attestation. LIVE/tenant-scoped data fail closed.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from portal import noc_correlation, noc_demo_rag, noc_runtime

router = APIRouter()
SCHEMA = "aiops.noc-signed-demo-context.v1"
TENANT_KEYS = frozenset({"tenant_id", "tenant", "organization_id", "org_id"})


def _result(state: str, reason: str, **details) -> dict:
    return {
        "schema": SCHEMA, "state": state, "reason": reason,
        "data_classification": "SYNTHETIC_SIMULATION_ONLY" if state == "SYNTHETIC_CONTEXT_ONLY" else "UNKNOWN",
        "citations": [], "tenant_acl_qualified": False,
        "source_runtime_observed": False, "llm_inference_performed": False,
        "grafana_observation": "NOT_TESTED", "runtime_authenticated": False,
        "production_qualified": False, "live_remediation_authorized": False,
        **details,
    }


def build_demo_context(noc: dict, run: dict, *, catalog=None) -> dict:
    """Never read fixtures until signed identities and DEMO mode are established."""
    if not isinstance(noc, dict) or noc.get("tenant_acl_qualified") is not False:
        raise ValueError("unqualified NOC scope")
    if not isinstance(run, dict) or TENANT_KEYS.intersection(run):
        raise ValueError("unqualified Core tenant scope")
    joined = noc_correlation.correlate(noc, run)
    if joined["state"] != "MATCHED_UNATTESTED":
        return _result("UNKNOWN", "CANONICAL_IDENTITY_MISMATCH")
    if joined["canonical_mode"] != "DEMO":
        return _result("UNKNOWN", "ONLY_CANONICAL_DEMO_RUNS_SUPPORTED")
    asset, event_key = noc.get("asset"), noc.get("event_key")
    if (not isinstance(asset, str) or noc_runtime.IDENTIFIER.fullmatch(asset) is None
            or not isinstance(event_key, str) or noc_runtime.IDENTIFIER.fullmatch(event_key) is None):
        return _result("UNKNOWN", "SIGNED_ASSET_OR_EVENT_ABSENT")
    rag = noc_demo_rag.build_demo_rag(asset, catalog=catalog)
    citations = [citation for citation in rag["citations"]
                 if citation["event_key"] == event_key]
    if not citations:
        return _result("UNKNOWN", "NO_EXACT_SYNTHETIC_ASSET_EVENT_CITATION")
    return _result(
        "SYNTHETIC_CONTEXT_ONLY", "SIGNED_IDENTITIES_AND_SYNTHETIC_EVENT_KEY_MATCH",
        citations=citations, asset=asset, event_key=event_key,
        canonical_run_id=joined["canonical_run_id"],
        canonical_incident_id=joined["canonical_incident_id"],
        noc_payload_sha256=joined["noc_payload_sha256"],
        catalog_sha256=rag["catalog_sha256"],
        source="SIGNED_NOC_CLAIM_PLUS_PR36_SYNTHETIC_FIXTURE",
    )


@router.get("/api/noc/demo-context", name="noc_signed_demo_context_readonly")
def noc_signed_demo_context(authorization: str | None = Header(default=None)):
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
        run = noc_correlation._read_core_run(noc["run_id"])
        result = build_demo_context(noc, run)
    except Exception:
        return noc_runtime._noc_json_response({"detail": "demo_context_unavailable_or_unverified"},
                                              status_code=503)
    return noc_runtime._noc_json_response(result)
