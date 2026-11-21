"""Offline synthetic CMDB/Twin edge proof gate: aiops2.twin-edge-proof.v1."""
from datetime import datetime
CONTRACT = "aiops2.twin-edge-proof.v1"
EXPECTED = {("SAN", "STORAGE"), ("STORAGE", "PAYMENTS")}

def _utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

def evaluate(payload, now, max_age_seconds=300):
    unknown = {"contract": CONTRACT, "status": "UNKNOWN", "path": [], "live_authorized": False}
    if not isinstance(payload, dict) or payload.get("contract") != CONTRACT or payload.get("mode") != "SIMULATION":
        return unknown
    tenant = payload.get("tenant")
    instant = _utc(now)
    edges = payload.get("edges")
    if not isinstance(tenant, str) or not tenant or instant is None or type(max_age_seconds) is not int or max_age_seconds < 0 or not isinstance(edges, list):
        return unknown
    found = {}
    for edge in edges:
        if not isinstance(edge, dict):
            return unknown
        pair = (edge.get("from_type"), edge.get("to_type"))
        stamp = _utc(edge.get("observed_at"))
        if pair not in EXPECTED or pair in found or stamp is None:
            return unknown
        age = (instant - stamp).total_seconds()
        if (edge.get("tenant") != tenant or edge.get("authority") != "CMDB" or
            edge.get("attested") is not True or
            not isinstance(edge.get("evidence_ref"), str) or not edge["evidence_ref"].strip() or
            not isinstance(edge.get("from_id"), str) or not edge["from_id"] or
            not isinstance(edge.get("to_id"), str) or not edge["to_id"] or
            age < 0 or age > max_age_seconds):
            return unknown
        found[pair] = edge
    if set(found) != EXPECTED:
        return unknown
    san, payment = found[("SAN", "STORAGE")], found[("STORAGE", "PAYMENTS")]
    if san["to_id"] != payment["from_id"]:
        return unknown
    return {"contract": CONTRACT, "status": "SOURCED_SYNTHETIC_PATH",
            "path": [san["from_id"], san["to_id"], payment["to_id"]], "live_authorized": False}
