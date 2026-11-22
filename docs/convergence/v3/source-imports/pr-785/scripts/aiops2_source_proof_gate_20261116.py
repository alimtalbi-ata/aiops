"""Offline-only versioned source proof gate; no network, adapters or effects."""
from datetime import datetime
import hashlib
import json

VERSION = "aiops2.source-proof-gate.v1"
SOURCES = frozenset(("checkmk", "prometheus", "grafana"))


def _utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
        return parsed if parsed.utcoffset().total_seconds() == 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def normalize(record, now, max_age_seconds=300):
    unknown = {"contract": VERSION, "status": "UNKNOWN", "identity": None,
               "incident_id": None, "causality": "UNKNOWN", "mode": "SIMULATION"}
    if not isinstance(record, dict) or not isinstance(max_age_seconds, int) or isinstance(max_age_seconds, bool) or max_age_seconds < 0:
        return unknown
    if record.get("mode") != "SIMULATION" or record.get("source") not in SOURCES:
        return unknown
    keys = ("tenant", "source", "instance", "event_id", "ci_id")
    if any(not isinstance(record.get(k), str) or not record[k].strip() for k in keys):
        return unknown
    observed, clock = _utc(record.get("observed_at")), _utc(now)
    if observed is None or clock is None:
        return unknown
    age = (clock - observed).total_seconds()
    if age < 0 or age > max_age_seconds:
        return unknown
    identity_payload = [record[k] for k in ("tenant", "source", "instance", "event_id")]
    identity = hashlib.sha256(json.dumps(identity_payload, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
    return {**unknown, "status": "SOURCED_SYNTHETIC", "identity": identity,
            "tenant": record["tenant"], "ci_id": record["ci_id"], "observed_at": record["observed_at"]}


def deduplicate(records):
    """Contradictory normalized duplicates stay UNKNOWN."""
    result = {}
    for record in records:
        identity = record.get("identity") if isinstance(record, dict) else None
        if not identity or record.get("status") != "SOURCED_SYNTHETIC":
            continue
        if identity not in result:
            result[identity] = dict(record)
        elif result[identity] != record:
            result[identity] = {"contract": VERSION, "status": "UNKNOWN", "identity": identity,
                                "incident_id": None, "causality": "UNKNOWN", "mode": "SIMULATION"}
    return list(result.values())


def correlate(records):
    """Candidate grouping is not a proven incident or causal chain."""
    records = list(records)
    if not records or any(not isinstance(r, dict) or r.get("status") != "SOURCED_SYNTHETIC" for r in records):
        return {"status": "UNKNOWN", "incident_id": None, "causality": "UNKNOWN"}
    if len({(r.get("tenant"), r.get("ci_id")) for r in records}) != 1:
        return {"status": "UNKNOWN", "incident_id": None, "causality": "UNKNOWN"}
    return {"status": "SYNTHETIC_CANDIDATE", "incident_id": None, "causality": "UNKNOWN"}
