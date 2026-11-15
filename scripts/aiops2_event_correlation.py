"""Deterministic, synthetic/offline AIOps event normalization and correlation.

No network, production integrations, actions or runtime attestation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re

SEVERITIES = frozenset({"P1", "P2", "P3", "P4"})
SOURCES = frozenset({"checkmk", "prometheus", "grafana"})
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class InvalidEvent(ValueError):
    """Event is not eligible for correlation."""


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise InvalidEvent("timestamp must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidEvent("invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InvalidEvent("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def normalize_event(raw: object) -> dict:
    """Validate a source event; reject ambiguity rather than guessing."""
    if not isinstance(raw, dict):
        raise InvalidEvent("event must be an object")
    for field in ("tenant_id", "source", "source_event_id", "ci_id", "service_id"):
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip():
            raise InvalidEvent(f"missing or invalid {field}")
    if raw["source"] not in SOURCES:
        raise InvalidEvent("unsupported source")
    if raw.get("severity") not in SEVERITIES:
        raise InvalidEvent("invalid severity")
    digest = raw.get("evidence_sha256")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise InvalidEvent("invalid evidence digest")
    observed = _timestamp(raw.get("observed_at"))
    known = _timestamp(raw.get("known_at"))
    if known < observed:
        raise InvalidEvent("known_at precedes observed_at")
    event = {field: raw[field] for field in (
        "tenant_id", "source", "source_event_id", "ci_id", "service_id",
        "severity", "evidence_sha256")}
    event["observed_at"] = observed.isoformat()
    event["known_at"] = known.isoformat()
    return event


def correlate_events(events: list, *, as_of: str, max_age_seconds: int = 900) -> dict:
    """Group eligible events by tenant and service; never infer Twin edges.

    This is a deterministic baseline, not causal/root-cause correlation.
    """
    if not isinstance(events, list):
        raise InvalidEvent("events must be a list")
    if not isinstance(max_age_seconds, int) or isinstance(max_age_seconds, bool) or max_age_seconds < 0:
        raise InvalidEvent("invalid max age")
    now = _timestamp(as_of)
    unique = {}
    rejected = []
    for index, raw in enumerate(events):
        try:
            event = normalize_event(raw)
            age = (now - _timestamp(event["observed_at"])).total_seconds()
            if age < 0 or age > max_age_seconds:
                raise InvalidEvent("event outside freshness window")
            if _timestamp(event["known_at"]) > now:
                raise InvalidEvent("event not yet known")
            key = (event["tenant_id"], event["source"], event["source_event_id"])
            if key in unique:
                if unique[key] != event:
                    raise InvalidEvent("conflicting duplicate event identity")
                continue
            unique[key] = event
        except InvalidEvent as exc:
            rejected.append({"index": index, "reason": str(exc)})
    groups = {}
    for event in unique.values():
        groups.setdefault((event["tenant_id"], event["service_id"]), []).append(event)
    incidents = []
    for (tenant, service), members in sorted(groups.items()):
        members.sort(key=lambda e: (e["observed_at"], e["source"], e["source_event_id"]))
        identity = json.dumps([tenant, service], separators=(",", ":"), ensure_ascii=True)
        incident_id = "SYN-" + hashlib.sha256(identity.encode()).hexdigest()[:16]
        incidents.append({
            "incident_id": incident_id,
            "tenant_id": tenant,
            "service_id": service,
            "priority": min((e["severity"] for e in members), key=lambda x: int(x[1:])),
            "event_count": len(members),
            "events": members,
            "impact_state": "UNKNOWN",
            "runtime_attested": False,
            "live_remediation_authorized": False,
        })
    return {
        "schema": "aiops2.synthetic-event-correlation.v1",
        "scope": "ISOLATED_DETERMINISTIC_NO_LIVE_EFFECTS",
        "incidents": incidents,
        "rejected": rejected,
        "runtime_attested": False,
        "live_remediation_authorized": False,
    }
