"""Validate an offline evidence manifest's structure, never its authenticity.

No network, DB, trust anchor, receipt acceptance, or operational permission.
A structurally valid manifest remains UNVERIFIED pending independent review.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from portal.acme_evidence_collection_plan import (
    EVIDENCE_REQUIREMENTS, plan_synthetic_evidence_collection,
)
from portal.acme_lifecycle_read_model import STAGES

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}\Z")


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("evidence_timestamp_not_utc")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("evidence_timestamp_invalid") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("evidence_timestamp_not_utc")
    return parsed


def inspect_synthetic_evidence_manifest(lifecycle: dict, manifest: object) -> dict:
    plan = plan_synthetic_evidence_collection(lifecycle)
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema", "mode", "source_sha256", "incident_id", "items"
    }:
        raise ValueError("evidence_manifest_shape")
    if (manifest["schema"] != "aiops.synthetic-evidence-manifest.v1"
            or manifest["mode"] != "DEMO"
            or manifest["source_sha256"] != plan["source_sha256"]
            or manifest["incident_id"] != plan["incident_id"]
            or not isinstance(manifest["items"], list)
            or len(manifest["items"]) > len(STAGES)):
        raise ValueError("evidence_manifest_scope")
    expected = {request["checkpoint"]: request for request in plan["requests"]}
    seen = set()
    inspected = []
    for item in manifest["items"]:
        if not isinstance(item, dict) or set(item) != {
            "checkpoint", "source", "evidence_type", "source_id",
            "observed_at", "content_sha256"
        }:
            raise ValueError("evidence_item_shape")
        cue = item["checkpoint"]
        if not isinstance(cue, str) or cue not in expected or cue in seen:
            raise ValueError("evidence_checkpoint_unknown_or_duplicate")
        seen.add(cue)
        request = expected[cue]
        if (item["source"] != request["expected_source"]
                or item["evidence_type"] != EVIDENCE_REQUIREMENTS[cue][0]
                or not isinstance(item["source_id"], str)
                or _ID.fullmatch(item["source_id"]) is None
                or not isinstance(item["content_sha256"], str)
                or _HEX.fullmatch(item["content_sha256"]) is None):
            raise ValueError("evidence_item_unqualified")
        _timestamp(item["observed_at"])
        inspected.append({
            "checkpoint": cue,
            "structurally_valid": True,
            "authenticity": "UNVERIFIED",
            "source_integrity_verified": False,
            "runtime_attested": False,
            "qualifies_transition": False,
        })
    return {
        "schema": "aiops.synthetic-evidence-manifest-inspection.v1",
        "mode": "DEMO",
        "source_sha256": plan["source_sha256"],
        "inspected_items": inspected,
        "structurally_valid_count": len(inspected),
        "independently_verified_count": 0,
        "unsubmitted_checkpoints": [cue for cue, _, _ in STAGES if cue not in seen],
        "overall_qualification": "UNKNOWN",
        "accepted_as_runtime_evidence": False,
        "itil_transition_authorized": False,
        "live_remediation_authorized": False,
    }
