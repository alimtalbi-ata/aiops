"""Normalize Core synthetic evidence-ref responses without inventing attestation.

No HTTP, database, authentication, tenant ACL or external effects. A qualified
Core response is still NOT tenant-authorized or runtime-attested.
"""
from __future__ import annotations
import re
from typing import Any

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SHA = re.compile(r"^[a-f0-9]{64}$")


def normalize_core_evidence_refs(
    receipt: dict[str, Any], response: dict[str, Any] | None
) -> dict[str, Any]:
    """Conservative presentation-only consistency check for Core read-model."""
    result = {
        "classification": "SYNTHETIC_UNVERIFIED",
        "status": "UNKNOWN",
        "reason": "MISSING_CORE_RESPONSE",
        "run_id": receipt.get("run_id") if isinstance(receipt, dict) else None,
        "matched_evidence_ids": [],
        "core_run_verified": False,
        "evidence_verified": False,
        "tenant_acl_qualified": False,
        "runtime_attested": False,
        "effect_applied": False,
    }
    if not isinstance(receipt, dict) or receipt.get("schema") != "aiops.acme-remediation-receipt.v1":
        raise ValueError("invalid_receipt")
    if not isinstance(response, dict):
        return result
    if (response.get("schema") != "aiops.core-demo-evidence-refs.v1"
            or response.get("classification") != "SYNTHETIC_ONLY"
            or response.get("run_id") != receipt.get("run_id")
            or response.get("tenant_acl_qualified") is not False
            or response.get("runtime_attested") is not False
            or response.get("event_link_verified") is not True):
        result["reason"] = "CORE_CONTRACT_MISMATCH"
        return result
    expected = receipt.get("evidence_ids")
    items = response.get("items")
    if (not isinstance(expected, list) or not expected or len(expected) > 32
            or any(not isinstance(x, str) or not _ID.fullmatch(x) for x in expected)
            or len(set(expected)) != len(expected)
            or not isinstance(items, list) or len(items) != len(expected)):
        result["reason"] = "EVIDENCE_SET_MISMATCH"
        return result
    seen = []
    for item in items:
        if (not isinstance(item, dict)
                or not isinstance(item.get("evidence_id"), str)
                or not _ID.fullmatch(item["evidence_id"])
                or not isinstance(item.get("source"), str)
                or not item["source"]
                or not isinstance(item.get("payload_sha256"), str)
                or not _SHA.fullmatch(item["payload_sha256"])
                or not isinstance(item.get("known_at"), str)
                or not item["known_at"]):
            result["reason"] = "CORE_ITEM_UNQUALIFIED"
            return result
        seen.append(item["evidence_id"])
    if len(set(seen)) != len(seen) or set(seen) != set(expected):
        result["reason"] = "EVIDENCE_SET_MISMATCH"
        return result
    result["status"] = "CONSISTENT_UNATTESTED"
    result["reason"] = "REFERENCES_MATCH_BUT_TENANT_ACL_AND_RUNTIME_UNVERIFIED"
    result["matched_evidence_ids"] = sorted(seen)
    return result
