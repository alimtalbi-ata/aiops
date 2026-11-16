"""Offline, synthetic-only AIOps source envelope contract. No I/O or LIVE capability."""
from datetime import datetime, timezone
import hashlib
import json

VERSION = "aiops2.source-envelope.v1"
SOURCES = frozenset(("checkmk", "prometheus", "grafana"))

def _utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("UTC_Z_REQUIRED")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("INVALID_TIMESTAMP") from exc
    if result.utcoffset().total_seconds() != 0:
        raise ValueError("UTC_REQUIRED")
    return result

def normalize(raw, *, now, max_age_seconds=300):
    """Return a deterministic immutable-by-convention envelope; reject unsafe evidence."""
    if type(max_age_seconds) is not int or max_age_seconds < 0:
        raise ValueError("INVALID_MAX_AGE")
    if not isinstance(raw, dict) or raw.get("contract_version") != VERSION:
        raise ValueError("INVALID_CONTRACT")
    if raw.get("mode") != "SIMULATION":
        raise ValueError("NO_LIVE")
    for field in ("tenant_id", "source_instance", "event_id", "ci_id"):
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("INVALID_" + field.upper())
    source = raw.get("source")
    if source not in SOURCES:
        raise ValueError("INVALID_SOURCE")
    observed = _utc(raw.get("observed_at"))
    clock = _utc(now)
    age = (clock - observed).total_seconds()
    if age < 0 or age > max_age_seconds:
        raise ValueError("UNTRUSTED_FRESHNESS")
    identity = [raw["tenant_id"], source, raw["source_instance"], raw["event_id"]]
    canonical = json.dumps(identity, ensure_ascii=False, separators=(",", ":"))
    key = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if "identity_key" in raw and raw["identity_key"] != key:
        raise ValueError("FORGED_IDENTITY")
    return {"contract_version": VERSION, "mode": "SIMULATION",
            "tenant_id": raw["tenant_id"], "source": source,
            "source_instance": raw["source_instance"], "event_id": raw["event_id"],
            "ci_id": raw["ci_id"], "observed_at": raw["observed_at"],
            "identity_key": key, "freshness": "FRESH_SYNTHETIC"}

def correlate(envelopes):
    """Group only same tenant+CI; no causal inference or incident creation."""
    groups = {}
    seen = {}
    for e in envelopes:
        if e.get("contract_version") != VERSION or e.get("mode") != "SIMULATION":
            raise ValueError("UNTRUSTED_ENVELOPE")
        key = e["identity_key"]
        fingerprint = tuple(e[k] for k in ("tenant_id", "source", "source_instance",
                                            "event_id", "ci_id", "observed_at"))
        if key in seen:
            if seen[key] != fingerprint:
                raise ValueError("CONTRADICTORY_DUPLICATE")
            continue
        seen[key] = fingerprint
        groups.setdefault((e["tenant_id"], e["ci_id"]), []).append(key)
    return [{"tenant_id": tenant, "ci_id": ci, "signal_keys": sorted(keys),
             "causality": "UNKNOWN", "incident_id": None}
            for (tenant, ci), keys in sorted(groups.items())]
