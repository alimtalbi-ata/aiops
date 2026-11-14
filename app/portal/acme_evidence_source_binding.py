"""Offline source-bound evidence receipt verification for DEMO.

A trusted key resolver must independently bind source and tenant to a secret.
A valid HMAC authenticates a receipt issued by that key holder, not a live
system observation, authorization, or independently verified remediation.
No HTTP endpoint, persistence, GLPI or Temporal side effects.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Callable

from portal.acme_evidence_manifest_validator import inspect_synthetic_evidence_manifest

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def inspect_source_bound_receipts(
    lifecycle: dict, manifest: object, receipts: object,
    resolve_key: Callable[[str, str], bytes],
) -> dict:
    inspected = inspect_synthetic_evidence_manifest(lifecycle, manifest)
    if not callable(resolve_key):
        raise ValueError("trusted_key_resolver_required")
    if not isinstance(receipts, list) or len(receipts) > 9:
        raise ValueError("invalid_receipt_batch")
    items = {item["checkpoint"]: item for item in manifest["items"]}
    seen = set()
    results = []
    for receipt in receipts:
        if not isinstance(receipt, dict) or set(receipt) != {
            "schema", "mode", "tenant_id", "checkpoint", "source", "source_id",
            "content_sha256", "observed_at", "source_sha256", "mac_sha256"
        }:
            raise ValueError("invalid_source_receipt_shape")
        cue = receipt["checkpoint"]
        if not isinstance(cue, str) or cue not in items or cue in seen:
            raise ValueError("unknown_or_duplicate_source_receipt")
        seen.add(cue)
        item = items[cue]
        tenant = receipt["tenant_id"]
        if (receipt["schema"] != "aiops.synthetic-source-bound-receipt.v1"
                or receipt["mode"] != "DEMO"
                or not isinstance(tenant, str) or _ID.fullmatch(tenant) is None
                or receipt["source"] != item["source"]
                or receipt["source_id"] != item["source_id"]
                or receipt["content_sha256"] != item["content_sha256"]
                or receipt["observed_at"] != item["observed_at"]
                or receipt["source_sha256"] != inspected["source_sha256"]
                or not isinstance(receipt["mac_sha256"], str)
                or _HEX.fullmatch(receipt["mac_sha256"]) is None):
            raise ValueError("source_receipt_binding_mismatch")
        signed = {key: value for key, value in receipt.items() if key != "mac_sha256"}
        # Missing/failed trust resolver means UNKNOWN, never a success.
        try:
            key = resolve_key(tenant, item["source"])
            if not isinstance(key, bytes) or len(key) < 32:
                raise ValueError("unqualified_source_key")
            expected = hmac.new(key, _canonical(signed), hashlib.sha256).hexdigest()
            state = ("MAC_VALID_SOURCE_KEY_UNATTESTED"
                     if hmac.compare_digest(expected, receipt["mac_sha256"])
                     else "MAC_MISMATCH")
        except Exception:
            state = "SOURCE_KEY_UNAVAILABLE"
        results.append({
            "checkpoint": cue,
            "receipt_integrity": state,
            "runtime_observation_independently_verified": False,
            "tenant_actor_authorized": False,
            "itil_transition_authorized": False,
        })
    return {
        "schema": "aiops.synthetic-source-bound-receipt-inspection.v1",
        "mode": "DEMO",
        "source_sha256": inspected["source_sha256"],
        "results": results,
        "valid_source_mac_count": sum(
            r["receipt_integrity"] == "MAC_VALID_SOURCE_KEY_UNATTESTED" for r in results
        ),
        "runtime_attested_count": 0,
        "evidence_accepted": False,
        "live_remediation_authorized": False,
    }
