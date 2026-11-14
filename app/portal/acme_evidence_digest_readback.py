"""Independent read-only digest comparison for untrusted DEMO evidence metadata.

A caller supplies a separately obtained readback function. Matching bytes prove
content consistency only, NOT source identity, tenancy, freshness or authorization.
No HTTP route, network client, persistence, evidence acceptance or LIVE action.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable

from portal.acme_evidence_manifest_validator import inspect_synthetic_evidence_manifest

MAX_READBACK_BYTES = 1024 * 1024


def compare_synthetic_evidence_readbacks(
    lifecycle: dict, manifest: object, readback: Callable[[str, str], bytes]
) -> dict:
    inspected = inspect_synthetic_evidence_manifest(lifecycle, manifest)
    if not callable(readback):
        raise ValueError("readback_callback_required")
    by_checkpoint = {item["checkpoint"]: item for item in manifest["items"]}
    comparisons = []
    for entry in inspected["inspected_items"]:
        cue = entry["checkpoint"]
        item = by_checkpoint[cue]
        try:
            payload = readback(item["source"], item["source_id"])
            if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_READBACK_BYTES:
                raise ValueError("invalid_readback_bytes")
            actual = hashlib.sha256(payload).hexdigest()
            state = "DIGEST_MATCH_UNATTESTED" if actual == item["content_sha256"] else "DIGEST_MISMATCH"
        except Exception:
            # The callback is an untrusted boundary; never return its exception,
            # partial content or credentials in a diagnostic response.
            state = "READBACK_UNAVAILABLE"
        comparisons.append({
            "checkpoint": cue,
            "comparison_state": state,
            "source_identity_authenticated": False,
            "tenant_scope_verified": False,
            "runtime_attested": False,
            "qualifies_itil_transition": False,
        })
    return {
        "schema": "aiops.synthetic-evidence-readback-comparison.v1",
        "mode": "DEMO",
        "source_sha256": inspected["source_sha256"],
        "comparisons": comparisons,
        "compared_count": len(comparisons),
        "digest_match_count": sum(
            c["comparison_state"] == "DIGEST_MATCH_UNATTESTED" for c in comparisons
        ),
        "independently_attested_count": 0,
        "evidence_accepted": False,
        "itil_transition_authorized": False,
        "live_remediation_authorized": False,
    }
