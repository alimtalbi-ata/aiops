"""Read-only Worker observation admission boundary; no IO or action dispatch.

Adapter contract only: caller obtains bridge data through its own authenticated read-only
transport. UNKNOWN never becomes an authorization or a fabricated observation.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json


def _utc(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo and parsed.utcoffset() is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def admit_observation(envelope, *, now, max_age_seconds=180, expected_run_id=None,
                      expected_tenant_id=None, expected_ticket_id=None):
    """Return immutable decision receipt; only ACCEPTED may feed Analyst.

    Caller must independently verify bridge authentication and signed provenance.
    An accepted envelope does not authorize remediation, ITSM writes, or HITL.
    """
    def receipt(status, reason, fingerprint=None):
        return {'status': status, 'reason': reason, 'fingerprint': fingerprint,\n                'run_id': expected_run_id, 'tenant_id': expected_tenant_id,\n                'ticket_id': expected_ticket_id}
    if not isinstance(envelope, dict) or not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        return receipt('UNKNOWN', 'MALFORMED_INPUT')
    if type(max_age_seconds) not in (int, float) or not 0 < max_age_seconds <= 86400:
        return receipt('UNKNOWN', 'INVALID_FRESHNESS_POLICY')
    for key, expected in [('run_id', expected_run_id), ('tenant_id', expected_tenant_id), ('ticket_id', expected_ticket_id)]:
        if expected is None or type(envelope.get(key)) is not type(expected) or envelope.get(key) != expected:
            return receipt('UNKNOWN', 'IDENTITY_MISMATCH')
    if type(expected_ticket_id) is not int or expected_ticket_id <= 0:
        return receipt('UNKNOWN', 'INVALID_TICKET')
    if envelope.get('source') != 'fs-lab' or envelope.get('access_mode') != 'read-only':
        return receipt('UNKNOWN', 'UNTRUSTED_SOURCE')
    if envelope.get('provenance_verified') is not True:
        return receipt('UNKNOWN', 'PROVENANCE_UNVERIFIED')
    observed = _utc(envelope.get('observed_at'))
    received = _utc(envelope.get('received_at'))
    now_utc = now.astimezone(timezone.utc)
    if observed is None or received is None or observed > received or received > now_utc:
        return receipt('UNKNOWN', 'INVALID_TIMESTAMPS')
    if (now_utc - observed).total_seconds() > max_age_seconds:
        return receipt('UNKNOWN', 'STALE_OBSERVATION')
    evidence = envelope.get('evidence')
    def has_signal(value, depth=0):
        if depth > 8:
            return False
        if isinstance(value, dict):
            return bool(value) and all(isinstance(k, str) and bool(k.strip()) and has_signal(v, depth + 1) for k, v in value.items())
        if isinstance(value, list):
            return bool(value) and all(has_signal(v, depth + 1) for v in value)
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, bool):
            return True
        if type(value) in (int, float):
            from math import isfinite
            return isfinite(value)
        return False
    if not isinstance(evidence, dict) or not has_signal(evidence) or not isinstance(envelope.get('source_event_id'), str) or not envelope['source_event_id'].strip():
        return receipt('UNKNOWN', 'INSUFFICIENT_EVIDENCE')
    try:
        canonical = json.dumps({k: envelope[k] for k in ('tenant_id', 'ticket_id', 'run_id', 'source', 'source_event_id', 'observed_at', 'evidence')}, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (ValueError, TypeError, KeyError):
        return receipt('UNKNOWN', 'NONCANONICAL_EVIDENCE')
    return receipt('ACCEPTED', 'READ_ONLY_OBSERVATION', sha256(canonical.encode()).hexdigest())
