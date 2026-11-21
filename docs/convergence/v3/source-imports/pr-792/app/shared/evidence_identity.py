"""Canonical evidence identity used by ingestion and replay-safe idempotency.

The payload alone is not an observation identity. It may be identical for
different CIs, incident runs, source identities, timestamps, or claims.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json


def normalize_observed_at(value: str | None) -> str | None:
    """An observed timestamp must be timezone-aware. UTC is canonical."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("observed_at_not_a_timestamp")
    try:
        parsed=datetime.fromisoformat(value.strip().replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at_invalid_iso8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observed_at_timezone_required")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00","Z")


def canonical_evidence(
    *, source: str, external_id: str | None, observed_at: str | None,
    claim: str, confidence: float, provenance: dict, payload: dict,
) -> dict:
    if not isinstance(source,str) or not source.strip():
        raise ValueError("source_required")
    if external_id is not None and (not isinstance(external_id,str) or not external_id.strip()):
        raise ValueError("external_id_must_be_nonempty_or_null")
    if not isinstance(claim,str) or not claim.strip():
        raise ValueError("claim_required")
    if not isinstance(provenance,dict) or not isinstance(payload,dict):
        raise ValueError("provenance_and_payload_must_be_objects")
    if "_aiops_quality" in provenance or "_aiops_quality" in payload:
        raise ValueError("caller_cannot_supply_computed_quality")
    return {
        "source":source.strip(),
        "external_id":external_id.strip() if external_id is not None else None,
        "observed_at":normalize_observed_at(observed_at),
        "claim":claim.strip(),
        "confidence":float(confidence),
        "provenance":provenance,
        "payload":payload,
    }


def evidence_digest(data: dict) -> str:
    packed=json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False)
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()
