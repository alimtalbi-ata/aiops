"""Fail-closed read-only qualification of an offline ACME receipt against caller-supplied Core snapshots.

Snapshots MUST originate from a separately authenticated, tenant-scoped Core read.
This function does not authenticate or fetch them. No writes or external I/O.
"""
from __future__ import annotations
from copy import deepcopy
from typing import Any

_ALLOWED = {"DEMO", "REPLAY", "STORY"}


def qualify_receipt(
    receipt: dict[str, Any],
    core_run: dict[str, Any] | None,
    core_evidence: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Never promote unverified fixture IDs to an attested runtime receipt."""
    if not isinstance(receipt, dict) or receipt.get("schema") != "aiops.acme-remediation-receipt.v1":
        raise ValueError("invalid_receipt_schema")
    result = deepcopy(receipt)
    result.update({
        "classification": "SYNTHETIC_UNVERIFIED",
        "core_run_verified": False,
        "evidence_verified": False,
        "core_snapshot_match": False,
        "evidence_snapshot_match": False,
        "qualification": "UNKNOWN",
        "qualification_reason": "MISSING_OR_UNTRUSTED_SNAPSHOTS",
        "runtime_attested": False,
        "production_qualified": False,
        "live_remediation_authorized": False,
        "effect_applied": False,
        "persisted": False,
    })
    if (receipt.get("classification") != "SYNTHETIC_UNVERIFIED"
            or receipt.get("core_run_verified") is not False
            or receipt.get("evidence_verified") is not False
            or receipt.get("effect_applied") is not False
            or receipt.get("persisted") is not False):
        result["qualification_reason"] = "UNSAFE_INPUT_CLAIMS"
        return result
    if not isinstance(core_run, dict) or not isinstance(core_evidence, list):
        return result
    if (core_run.get("run_id") != receipt.get("run_id")
            or core_run.get("scenario_id") != receipt.get("scenario_id")
            or core_run.get("mode") != receipt.get("projection", {}).get("mode")
            or core_run.get("mode") not in _ALLOWED
            or core_run.get("synthetic") is not True):
        result["qualification_reason"] = "CORE_IDENTITY_MISMATCH"
        return result
    result["core_snapshot_match"] = True
    expected = receipt.get("evidence_ids")
    if (not isinstance(expected, list) or not expected
            or any(not isinstance(x, str) for x in expected)
            or len(set(expected)) != len(expected)
            or len(core_evidence) != len(expected)):
        result["qualification_reason"] = "EVIDENCE_SET_MISMATCH"
        return result
    actual = []
    for item in core_evidence:
        if (not isinstance(item, dict)
                or item.get("run_id") != receipt["run_id"]
                or item.get("synthetic") is not True
                or item.get("source_qualified") is not True
                or not isinstance(item.get("evidence_id"), str)):
            result["qualification_reason"] = "EVIDENCE_UNQUALIFIED"
            return result
        actual.append(item["evidence_id"])
    if len(set(actual)) != len(actual) or set(actual) != set(expected):
        result["qualification_reason"] = "EVIDENCE_SET_MISMATCH"
        return result
    result["evidence_snapshot_match"] = True
    result["qualification"] = "SNAPSHOT_CONSISTENT_NOT_ATTESTED"
    result["qualification_reason"] = "CALLER_SUPPLIED_SNAPSHOTS_NOT_AUTHENTICATED_HERE"
    # Intentionally leave core_run_verified/evidence_verified false:
    # consistency is not authentication, freshness, tenant scope or attestation.
    return result
