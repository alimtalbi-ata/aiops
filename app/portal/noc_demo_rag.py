"""Read-only, synthetic-only NOC RAG fixture drilldown ported from PR #36.

A catalog citation is not observed evidence, vendor authority, or LLM inference.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from portal import noc_runtime

router = APIRouter()
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "noc_rag_synthetic.json"
MAX_CATALOG_BYTES = 128 * 1024
CATALOG_SCHEMA = "aiops-rag-ops-synthetic-fixtures-v1"
SCHEMA = "aiops.noc-demo-rag-drilldown.v1"
REQUIRED = {"doc_id", "vendor", "product", "kind", "signal_type", "event_key",
            "sample", "asset", "service", "runbook", "source_type"}
KINDS = {"EVENT_CATALOG", "RUNBOOK", "SNMP_MIB"}
SIGNALS = {"SYSLOG", "SNMP_TRAP", "METRIC", "LOG"}


def validate_catalog(data: object) -> list[dict]:
    """Adapt PR #36's strict synthetic catalog validator, without live fallback."""
    if (not isinstance(data, dict) or set(data) != {"schema", "provenance", "scenarios"}
            or data["schema"] != CATALOG_SCHEMA
            or data["provenance"] != "SYNTHETIC_SIMULATION_ONLY"):
        raise ValueError("invalid synthetic RAG catalog")
    rows = data["scenarios"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValueError("invalid synthetic catalog size")
    seen_docs: set[str] = set()
    seen_events: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != REQUIRED:
            raise ValueError("invalid catalog row")
        if (row["source_type"] != "SYNTHETIC"
                or not isinstance(row["kind"], str) or row["kind"] not in KINDS
                or not isinstance(row["signal_type"], str) or row["signal_type"] not in SIGNALS):
            raise ValueError("unverified catalog authority")
        for field in REQUIRED - {"runbook"}:
            value = row[field]
            if not isinstance(value, str) or not 1 <= len(value) <= 1024:
                raise ValueError("invalid catalog field")
        if (not row["sample"].startswith("DEMO ONLY:")
                or noc_runtime.IDENTIFIER.fullmatch(row["asset"]) is None
                or noc_runtime.IDENTIFIER.fullmatch(row["doc_id"]) is None
                or row["doc_id"] in seen_docs or row["event_key"] in seen_events):
            raise ValueError("duplicate or unsafe synthetic citation")
        steps = row["runbook"]
        if (not isinstance(steps, list) or not 1 <= len(steps) <= 20
                or any(not isinstance(s, str) or not 1 <= len(s) <= 200 for s in steps)):
            raise ValueError("invalid synthetic runbook")
        seen_docs.add(row["doc_id"])
        seen_events.add(row["event_key"])
    return rows


def load_catalog() -> tuple[list[dict], str]:
    raw = FIXTURE_PATH.read_bytes()
    if not raw or len(raw) > MAX_CATALOG_BYTES:
        raise ValueError("invalid catalog bytes")
    data = json.loads(raw.decode("utf-8"),
                      object_pairs_hook=noc_runtime._reject_duplicate_keys,
                      parse_constant=noc_runtime._reject_json_constant)
    return validate_catalog(data), hashlib.sha256(raw).hexdigest()


def build_demo_rag(asset: str, *, catalog: tuple[list[dict], str] | None = None) -> dict:
    if not isinstance(asset, str) or noc_runtime.IDENTIFIER.fullmatch(asset) is None:
        raise ValueError("invalid asset identifier")
    rows, catalog_sha = load_catalog() if catalog is None else catalog
    validate_catalog({"schema": CATALOG_SCHEMA, "provenance": "SYNTHETIC_SIMULATION_ONLY",
                      "scenarios": rows})
    if not isinstance(catalog_sha, str) or noc_runtime.SHA256.fullmatch(catalog_sha) is None:
        raise ValueError("invalid catalog digest")
    citations = []
    for row in rows:
        if row["asset"] != asset:
            continue
        doc_digest = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False,
                                              separators=(",", ":")).encode("utf-8")).hexdigest()
        citations.append({"doc_id": row["doc_id"], "doc_sha256": doc_digest,
                          "asset": row["asset"], "event_key": row["event_key"],
                          "vendor_label_unverified": row["vendor"],
                          "product_label_unverified": row["product"],
                          "sample": row["sample"], "runbook": row["runbook"],
                          "provenance": "SYNTHETIC_SIMULATION_ONLY"})
    return {"schema": SCHEMA, "state": "SYNTHETIC_REFERENCE_ONLY" if citations else "UNKNOWN",
            "reason": "EXACT_ASSET_FIXTURE_MATCH" if citations else "NO_MATCHING_SYNTHETIC_FIXTURE",
            "asset": asset, "catalog_sha256": catalog_sha, "citations": citations,
            "data_classification": "SYNTHETIC_SIMULATION_ONLY",
            "source": "PR36_PORTED_SYNTHETIC_RAG_FIXTURES",
            "tenant_acl_qualified": False, "source_runtime_observed": False,
            "llm_inference_performed": False, "grafana_observation": "NOT_TESTED",
            "runtime_authenticated": False, "production_qualified": False,
            "live_remediation_authorized": False}


@router.get("/api/noc/demo-rag", name="noc_synthetic_rag_drilldown")
def noc_demo_rag(asset: str, authorization: str | None = Header(default=None)):
    try:
        noc_runtime._require_portal_read_auth(authorization)
    except HTTPException as exc:
        return noc_runtime._noc_json_response({"detail": exc.detail}, status_code=exc.status_code)
    if noc_runtime.IDENTIFIER.fullmatch(asset) is None:
        return noc_runtime._noc_json_response({"detail": "invalid_asset_identifier"}, status_code=400)
    try:
        return noc_runtime._noc_json_response(build_demo_rag(asset))
    except (ValueError, OSError, UnicodeError, TypeError):
        return noc_runtime._noc_json_response({"detail": "synthetic_rag_catalog_unavailable_or_invalid"},
                                              status_code=503)
