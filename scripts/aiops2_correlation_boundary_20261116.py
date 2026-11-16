"""Offline deterministic synthetic incident-correlation boundary (v1).

No I/O, adapters, credentials, network or LIVE authority.
"""
from datetime import datetime
import hashlib
import json
import math

CONTRACT = 'aiops2.synthetic-correlation.v1'
SOURCES = frozenset({'checkmk', 'prometheus', 'grafana'})
MODES = frozenset({'DEMO', 'SIMULATION', 'REPLAY'})


def _utc(value):
    if not isinstance(value, str) or not value.endswith('Z'):
        raise ValueError('timestamp must be UTC Z string')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('invalid timestamp') from exc
    if result.utcoffset().total_seconds() != 0:
        raise ValueError('timestamp must be UTC')
    return result


def correlate(events, *, now, max_age_seconds=300, mode='SIMULATION'):
    """Join only explicit tenant+CI matches, never infer causality or impact."""
    if mode not in MODES:
        raise ValueError('mode denied')
    if type(max_age_seconds) not in (int, float) or not math.isfinite(max_age_seconds) or max_age_seconds < 0:
        raise ValueError('invalid freshness threshold')
    reference = _utc(now)
    if not isinstance(events, list):
        raise ValueError('events must be a list')
    groups, seen, unknown = {}, {}, []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            unknown.append({'index': index, 'reason': 'INVALID_EVENT'})
            continue
        required = ('tenant_id', 'source', 'source_instance', 'event_id', 'ci_id', 'observed_at')
        if any(not isinstance(event.get(k), str) or not event[k].strip() for k in required):
            unknown.append({'index': index, 'reason': 'MISSING_IDENTITY'})
            continue
        if event['source'] not in SOURCES:
            unknown.append({'index': index, 'reason': 'UNKNOWN_SOURCE'})
            continue
        try:
            observed = _utc(event['observed_at'])
        except ValueError:
            unknown.append({'index': index, 'reason': 'INVALID_TIME'})
            continue
        age = (reference - observed).total_seconds()
        if age < 0 or age > max_age_seconds:
            unknown.append({'index': index, 'reason': 'FRESHNESS_UNKNOWN'})
            continue
        identity = tuple(event[k] for k in required[:4])
        canonical = json.dumps(event, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
        digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        if identity in seen:
            if seen[identity] != digest:
                unknown.append({'index': index, 'reason': 'CONTRADICTORY_DUPLICATE'})
            continue
        seen[identity] = digest
        key = (event['tenant_id'], event['ci_id'])
        groups.setdefault(key, []).append({
            'source': event['source'], 'event_id': event['event_id'],
            'source_instance': event['source_instance']})
    return {
        'contract_version': CONTRACT, 'mode': mode,
        'correlation': [
            {'tenant_id': tenant, 'ci_id': ci,
             'signals': sorted(signals, key=lambda s: (s['source'], s['source_instance'], s['event_id'])),
             'causality': 'UNKNOWN', 'impact': 'UNKNOWN'}
            for (tenant, ci), signals in sorted(groups.items())
        ],
        'unknown': unknown, 'live_authorized': False,
    }
