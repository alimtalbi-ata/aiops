"""Offline synthetic signal envelope guard v1; not a LIVE adapter."""
from datetime import datetime
import hashlib
import json

SCHEMA = "aiops2.signal-envelope.v1"
SOURCES = frozenset(("checkmk", "prometheus", "grafana"))

def _utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be UTC Z")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.utcoffset().total_seconds() != 0:
        raise ValueError("timestamp offset")
    return dt

def normalize(event, *, now, max_age_seconds=900):
    """Reject untrusted envelopes; missing freshness becomes UNKNOWN."""
    required = {"schema", "mode", "tenant", "source", "source_instance", "event_id", "observed_at", "kind", "state", "metric"}
    if type(event) is not dict or set(event) != required:
        raise ValueError("invalid envelope keys")
    if event["schema"] != SCHEMA or event["mode"] not in ("DEMO", "SIMULATION", "REPLAY"):
        raise ValueError("schema/mode not permitted")
    for field in ("tenant", "source_instance", "event_id"):
        if type(event[field]) is not str or not event[field].strip() or len(event[field]) > 128:
            raise ValueError("missing identity")
    if event["source"] not in SOURCES or event["kind"] not in ("alert", "metric"):
        raise ValueError("source/kind")
    if event["state"] not in ("FIRING", "RESOLVED", "UNKNOWN"):
        raise ValueError("state")
    metric = event["metric"]
    if event["kind"] == "metric":
        if type(metric) is not dict or set(metric) != {"name", "value", "unit", "window_seconds"}:
            raise ValueError("metric contract")
        if not isinstance(metric["name"], str) or not metric["name"] or not isinstance(metric["unit"], str) or not metric["unit"]:
            raise ValueError("metric identity/unit")
        if type(metric["value"]) not in (int, float) or not (-1e300 < metric["value"] < 1e300):
            raise ValueError("metric value")
        if type(metric["window_seconds"]) is not int or not 0 < metric["window_seconds"] <= 86400:
            raise ValueError("metric window")
    elif metric is not None:
        raise ValueError("unexpected metric")
    age = (_utc(now) - _utc(event["observed_at"])).total_seconds()
    freshness = "FRESH" if 0 <= age <= max_age_seconds else "UNKNOWN"
    result = dict(event)
    result["freshness"] = freshness
    result["state"] = event["state"] if freshness == "FRESH" else "UNKNOWN"
    result["identity_key"] = [event[k] for k in ("tenant", "source", "source_instance", "event_id")]
    return result

def deduplicate(events):
    """Deduplicate identical events; reject conflicting duplicates."""
    seen = {}
    for event in events:
        key = tuple(event["identity_key"])
        digest = hashlib.sha256(json.dumps(event, sort_keys=True, allow_nan=False).encode()).hexdigest()
        if key in seen and seen[key][0] != digest:
            raise ValueError("contradictory duplicate")
        seen[key] = (digest, event)
    return [value[1] for value in seen.values()]
