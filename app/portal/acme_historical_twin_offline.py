"""Golden #802 f594d04e02abde19b2299fbb523bf9d0d0e360b8, offline historical predicates only."""
import hashlib, hmac, json, re
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from worker.acme_simulated_hitl import canonical_source_ids
TENANT, SCENARIO, ISSUER = 'ACME-TEST', 'ACME-SAN-PAYMENTS', 'TWIN_ACME_SIMULATED'
ROOT, PAYMENTS = 'ACME-TEST-SAN-FABRIC-A', 'ACME-TEST-SVC-PAYMENTS'
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{2,99}\Z', re.ASCII)

def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()

def approval_id(attempt):
    return 'SIM-APP-' + hashlib.sha256((TENANT + ':' + attempt).encode()).hexdigest()[:24].upper()

def utc(value):
    try:
        result = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        raise HTTPException(503, 'sandbox_approval_time_invalid') from None
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise HTTPException(503, 'sandbox_approval_time_invalid')
    return result.astimezone(timezone.utc)

def verified_record(value, *, attempt_id, key, now):
    try:
        doc = json.loads(value) if isinstance(value, str) else value
        payload, signature = doc['payload'], doc['signature']
        if not isinstance(payload, dict) or not isinstance(signature, str):
            raise ValueError('shape')
        if not hmac.compare_digest(hmac.new(key, canonical(payload), hashlib.sha256).hexdigest(), signature):
            raise ValueError('signature')
        if (payload.get('attempt_id') != attempt_id
                or payload.get('tenant_id') != TENANT
                or payload.get('scenario_id') != SCENARIO
                or payload.get('approval_id') != approval_id(attempt_id)
                or payload.get('idempotency_key') != attempt_id
                or any(type(payload.get(k)) is not str
                       or ID.fullmatch(payload[k]) is None
                       for k in ('incident_id', 'run_id', 'ticket_id', 'proposal_id'))
                or not payload['ticket_id'].startswith('SIM-GLPI-')
                or payload.get('approval_issuer') != ISSUER
                or payload.get('issuer_id') != 'twin-acme-test'
                or payload.get('approval_actor') != ISSUER
                or payload.get('approval_kind') != 'SIMULATED'
                or payload.get('approval_status') != 'SIMULATED'
                or payload.get('approval_phase') != 'PRE_RESOLUTION'
                or payload.get('core_status_at_issuance') != 'PREPARED'
                or payload.get('resolution_verified') is not False
                or payload.get('post_resolution_readback_required') is not True
                or payload.get('mode') != 'SIMULATION'
                or payload.get('human_approved') is not False
                or payload.get('execution_allowed') is not False
                or payload.get('effect_allowed') is not False
                or payload.get('live_effects_allowed') is not False
                or payload.get('real_glpi_writes_allowed') is not False
                or type(payload.get('core_request_sha256')) is not str
                or re.fullmatch(r'[0-9a-f]{64}', payload['core_request_sha256']) is None
                or type(payload.get('core_source_event_ids')) is not list
                or len(payload['core_source_event_ids']) != 7
                or payload['core_source_event_ids'] != canonical_source_ids(attempt_id)
                or len(set(str(v) for v in payload['core_source_event_ids'])) != 7
                or any(type(v) is not str or not v.startswith('SYN-EVT-')
                       or ID.fullmatch(v) is None for v in payload['core_source_event_ids'])
                or payload.get('impact_root') != ROOT
                or PAYMENTS not in payload.get('impacted_cis', [])
                or not isinstance(payload.get('approval_nonce'), str)
                or not ID.fullmatch(payload['approval_nonce'])):
            raise ValueError('binding')
        issued, expires = utc(payload['issued_at']), utc(payload['expires_at'])
        if issued > now:
            raise ValueError('future')
        if (issued > now + timedelta(seconds=30) or expires <= now
                or expires <= issued or expires - issued > timedelta(minutes=5)):
            raise ValueError('expired')
        return payload
    except (KeyError, ValueError, TypeError, AttributeError):
        raise HTTPException(503, 'sandbox_approval_unqualified') from None

def check_core(core, x):
    """Approval is PRE-RESOLUTION. A resolved or foreign Run cannot authorize it."""
    if not isinstance(core, dict):
        raise HTTPException(503, 'core_sandbox_authority_unqualified')
    event_ids = core.get('source_event_ids')
    if (core.get('attempt_id') != x.attempt_id
            or core.get('tenant_id') != TENANT
            or core.get('approval_issuer') != ISSUER
            or core.get('incident_id') != x.incident_id
            or core.get('run_id') != x.run_id
            or core.get('ticket_id') != x.ticket_id
            or core.get('proposal_id') != x.proposal_id
            or core.get('ticket_authority') != 'SIMULATED_ONLY'
            or core.get('ticket_status') != 'PREPARED'
            or core.get('incident_status') != 'PREPARED'
            or core.get('run_status') != 'PREPARED'
            or core.get('source') != 'SYNTHETIC_SIMULATOR'
            or type(core.get('source_event_count')) is not int
            or core['source_event_count'] != 7
            or core.get('source_hashes_qualified') is not True
            or type(event_ids) is not list or len(event_ids) != 7
            or event_ids != canonical_source_ids(x.attempt_id)
            or len(set(str(v) for v in event_ids)) != 7
            or any(type(v) is not str or not v.startswith('SYN-EVT-')
                   or ID.fullmatch(v) is None for v in event_ids)
            or type(core.get('request_sha256')) is not str
            or re.fullmatch(r'[0-9a-f]{64}', core['request_sha256']) is None
            or core.get('human_approved') is not False
            or core.get('execution_allowed') is not False
            or core.get('effect_allowed') is not False
            or core.get('live_effects_allowed') is not False
            or core.get('real_glpi_writes_allowed') is not False
            or core.get('analysis_validated') is not True
            or core.get('critic_validated') is not True
            or type(core.get('evidence_count')) is not int
            or core['evidence_count'] < 2):
        raise HTTPException(503, 'core_prepared_authority_unqualified')
    return (core['request_sha256'], tuple(event_ids))

def check_core_fence(x, core_readback):
    """Two independent Core GETs must agree before any Twin approval write."""
    first = core_readback(x)
    fingerprint = check_core(first, x)
    second = core_readback(x)
    if check_core(second, x) != fingerprint:
        raise HTTPException(503, 'core_prepared_snapshot_changed')
    return fingerprint

