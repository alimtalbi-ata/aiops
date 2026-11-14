"""Joint offline evidence qualification: byte digest AND source-bound MAC.

Matching bytes and a valid MAC are independent checks, but their conjunction
does not establish source freshness, tenant/actor authorization or LIVE proof.
"""
from __future__ import annotations

from collections.abc import Callable
import re

from portal.acme_evidence_digest_readback import compare_synthetic_evidence_readbacks
from portal.acme_evidence_source_binding import inspect_source_bound_receipts


def qualify_synthetic_evidence_jointly(
    lifecycle: dict, manifest: object, receipts: object,
    readback: Callable[[str, str], bytes],
    resolve_key: Callable[[str, str], bytes],
    *, expected_tenant_id: str,
) -> dict:
    # Both components independently validate the complete manifest before any
    # source callback. Structural invalidity never results in a partial success.
    from portal.acme_evidence_manifest_validator import inspect_synthetic_evidence_manifest
    inspect_synthetic_evidence_manifest(lifecycle, manifest)
    if (not isinstance(expected_tenant_id, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}", expected_tenant_id) is None):
        raise ValueError("trusted_expected_tenant_required")
    if not isinstance(receipts, list):
        raise ValueError("invalid_receipts")
    # A valid MAC for tenant B must not qualify in tenant A.
    # Check trusted tenant scope before any callback.
    if any(not isinstance(receipt, dict)
           or receipt.get("tenant_id") != expected_tenant_id for receipt in receipts):
        raise ValueError("receipt_tenant_scope_mismatch")
    # Validate and authenticate receipts first. A bad MAC must never be used to
    # justify an operational decision even if a separate byte digest matches.
    signed = inspect_source_bound_receipts(lifecycle, manifest, receipts, resolve_key)
    digests = compare_synthetic_evidence_readbacks(lifecycle, manifest, readback)
    by_digest = {item["checkpoint"]: item for item in digests["comparisons"]}
    by_mac = {item["checkpoint"]: item for item in signed["results"]}
    if len(by_digest) != len(digests["comparisons"]) or len(by_mac) != len(signed["results"]):
        raise ValueError("duplicate_joint_checkpoint")
    rows = []
    for item in manifest["items"]:
        cue = item["checkpoint"]
        digest_state = by_digest[cue]["comparison_state"]
        mac_state = (by_mac[cue]["receipt_integrity"] if cue in by_mac
                     else "SOURCE_RECEIPT_MISSING")
        both = (digest_state == "DIGEST_MATCH_UNATTESTED"
                and mac_state == "MAC_VALID_SOURCE_KEY_UNATTESTED")
        rows.append({
            "checkpoint": cue,
            "digest_state": digest_state,
            "source_receipt_state": mac_state,
            "integrity_consistent_unattested": both,
            "runtime_observation_independently_verified": False,
            "tenant_actor_authorized": False,
            "itil_transition_authorized": False,
        })
    return {
        "schema": "aiops.synthetic-evidence-joint-qualification.v1",
        "mode": "DEMO",
        "expected_tenant_id": expected_tenant_id,
        "source_sha256": digests["source_sha256"],
        "checkpoints": rows,
        "integrity_consistent_unattested_count": sum(
            item["integrity_consistent_unattested"] for item in rows
        ),
        "independently_attested_count": 0,
        "overall_qualification": "UNKNOWN",
        "evidence_accepted": False,
        "itil_transition_authorized": False,
        "live_remediation_authorized": False,
    }
