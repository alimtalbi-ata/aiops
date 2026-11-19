"""Deterministic synthetic signal normalization; no collectors or runtime authority."""
from datetime import datetime, timezone
import hashlib
import json
import re

SCHEMA = "aiops.acme.signal-context.v1"
FIELDS = {"source", "event_id", "namespace", "ci_id", "state", "severity", "observed_at"}
SOURCES = {"GRAFANA_FIXTURE", "PROMETHEUS_FIXTURE"}
SEVERITIES = {"critical": "P1", "warning": "P2", "info": "P3"}
CLOCK = "2026-10-25T09:00:00Z"
MAX_AGE_SECONDS = 300


def _utc(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise ValueError("invalid_signal_utc")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def normalize_signals(events, twin, *, as_of_utc, max_age_seconds=MAX_AGE_SECONDS):
    """Normalize a bounded fixture batch; deduplicate exact source-scoped IDs.

    Conflicting replays, unknown CI and cross-namespace inputs fail closed.
    Freshness refers only to an explicit scenario clock, not wall-clock health.
    """
    if type(max_age_seconds) is not int or not 0 <= max_age_seconds <= 86400:
        raise ValueError("invalid_signal_age_limit")
    now = _utc(as_of_utc)
    if not isinstance(events, list) or len(events) > 1000:
        raise ValueError("invalid_signal_batch")
    digest = twin.get("source_sha256")
    incident_id = twin.get("incident_id")
    impact_incident_id = twin.get("impact_incident_id")
    expected_run = "SIM-ACME-" + digest[:16].upper() if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) else None
    if (twin.get("scope") != "STORY_OFFLINE" or twin.get("namespace") != "ACME-DEMO"
            or twin.get("runtime_attested") is not False or twin.get("binding_status") != "UNBOUND"
            or twin.get("tenant_id") is not None or twin.get("attempt_id") is not None
            or twin.get("core_run_id") is not None or twin.get("resource_id") is not None
            or twin.get("service_id") is not None or twin.get("source_sha") is not None
            or twin.get("observed_at") is not None or twin.get("freshness") != "UNKNOWN"
            or twin.get("run_id") != expected_run or not isinstance(incident_id, str)
            or not isinstance(impact_incident_id, str)):
        raise ValueError("invalid_signal_scope")
    ids = {n["node_id"] for n in twin["nodes"]}
    affected = set(twin["impact"]["affected_ci_ids"])
    entries = {}
    for event in events:
        if not isinstance(event, dict) or set(event) != FIELDS:
            raise ValueError("invalid_signal_fields")
        if (not all(isinstance(event[k], str) for k in FIELDS - {"observed_at"})
                or event["source"] not in SOURCES or event["namespace"] != twin["namespace"]
                or event["ci_id"] not in ids or event["severity"] not in SEVERITIES
                or event["state"] not in {"firing", "resolved"}
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", event["event_id"])):
            raise ValueError("invalid_signal_identity")
        age = None if event["observed_at"] is None else int((now - _utc(event["observed_at"])).total_seconds())
        if age is not None and age < 0:
            raise ValueError("future_signal_observation")
        key = (event["namespace"], event["source"], event["event_id"])
        digest = _digest(event)
        if key in entries:
            if entries[key]["provenance"]["event_sha256"] != digest:
                raise ValueError("conflicting_signal_replay")
            continue
        entries[key] = {
            "signal_id": _digest(list(key)), "source": event["source"],
            "event_id": event["event_id"], "ci_id": event["ci_id"],
            "priority": SEVERITIES[event["severity"]], "state": event["state"].upper(),
            "scenario_freshness": {"status": "UNKNOWN" if age is None else "FRESH" if age <= max_age_seconds else "STALE",
                                   "age_seconds": age, "observed_at": event["observed_at"]},
            "runtime_freshness": "UNKNOWN",
            "correlation": "STRUCTURALLY_RELATED" if event["ci_id"] in affected else "OUTSIDE_IMPACT_PATH",
            "provenance": {"scope": "STORY_OFFLINE", "namespace": event["namespace"],
                           "source": event["source"], "source_ref": "inline://synthetic/" + event["source"] + "/" + event["event_id"],
                           "event_sha256": digest, "observed_at": event["observed_at"],
                           "twin_source_sha256": twin["source_sha256"],
                           "source_kind": "SYNTHETIC_EVENT_NOT_COLLECTED"},
        }
    signals = [entries[k] for k in sorted(entries)]
    return {"schema": SCHEMA, "scope": "STORY_OFFLINE", "namespace": twin["namespace"],
            "tenant_id": None, "incident_id": incident_id, "impact_incident_id": impact_incident_id,
            "run_id": twin["run_id"], "attempt_id": None, "binding_status": "UNBOUND",
            "source_sha256": twin["source_sha256"],
            "scenario_as_of_utc": as_of_utc, "max_age_seconds": max_age_seconds,
            "input_count": len(events), "unique_count": len(signals), "duplicate_count": len(events)-len(signals),
            "signals": signals, "runtime_attested": False, "live_remediation_authorized": False}


def build_signal_context(twin):
    """Synthetic demonstration inputs, separate from the canonical topology fixture."""
    san = {"source": "GRAFANA_FIXTURE", "event_id": "SAN-P1", "namespace": "ACME-DEMO",
           "ci_id": "SAN-FABRIC-A", "state": "firing", "severity": "critical",
           "observed_at": "2026-10-25T08:59:00Z"}
    payments = {**san, "source": "PROMETHEUS_FIXTURE", "event_id": "PAY-P2",
                "ci_id": "APP-PAY-01", "severity": "warning", "observed_at": None}
    return normalize_signals([san, dict(san), payments], twin, as_of_utc=CLOCK)
