"""Grafana alert evidence collector: injected read-only transport, no network defaults.

A successful projection is metadata validation, not an authenticated runtime attestation.
The caller must establish the transport's identity, tenant isolation and TLS.
"""
import hashlib
import json
from datetime import datetime, timezone


def _utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("grafana_timestamp_invalid")
    try:
        dt = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("grafana_timestamp_invalid") from exc
    if dt.utcoffset() != timezone.utc.utcoffset(dt):
        raise ValueError("grafana_timestamp_invalid")
    return dt


def collect_grafana_alert_readonly(*, fetch_alert, rule_uid, tenant_id,
                                   service_identity, max_age_seconds,
                                   now_utc, expected_fingerprint=None):
    """Fetch one existing alert through an injected, already authorized GET-only callback.

    The callback receives (rule_uid, tenant_id); this module never issues HTTP,
    handles credentials, or creates/updates alert rules.
    """
    if (not callable(fetch_alert) or not all(
            isinstance(v, str) and v.strip()
            for v in (rule_uid, tenant_id, service_identity))
            or not isinstance(max_age_seconds, int) or isinstance(max_age_seconds, bool)
            or not 0 < max_age_seconds <= 3600):
        raise ValueError("grafana_request_scope_invalid")
    now = _utc(now_utc)
    payload = fetch_alert(rule_uid, tenant_id)
    if not isinstance(payload, dict):
        raise ValueError("grafana_response_invalid")
    if payload.get("rule_uid") != rule_uid or payload.get("tenant_id") != tenant_id:
        raise ValueError("grafana_tenant_or_rule_mismatch")
    if payload.get("state") not in ("firing", "pending", "normal"):
        raise ValueError("grafana_alert_state_invalid")
    dashboard_uid = payload.get("dashboard_uid")
    observed_at = payload.get("observed_at_utc")
    if not isinstance(dashboard_uid, str) or not dashboard_uid.strip():
        raise ValueError("grafana_dashboard_uid_missing")
    observed = _utc(observed_at)
    age = (now - observed).total_seconds()
    if age < 0 or age > max_age_seconds:
        raise ValueError("grafana_alert_stale_or_future")
    # Canonical bytes are a local projection digest, not a signature of origin.
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    if expected_fingerprint is not None and expected_fingerprint != digest:
        raise ValueError("grafana_fingerprint_mismatch")
    return {
        "schema": "aiops2.grafana-alert-evidence.v1",
        "status": "UNATTESTED",
        "source": "GRAFANA_READ_ONLY_INJECTED_TRANSPORT",
        "tenant_scope": tenant_id,
        "rule_uid": rule_uid,
        "dashboard_uid": dashboard_uid,
        "alert_state": payload["state"],
        "observed_at_utc": observed_at,
        "service_identity": service_identity,
        "response_sha256": digest,
        "runtime_attested": False,
        "native_tenant_acl_verified": False,
        "live_actions_authorized": False,
    }
