"""Pure INT-06A consumer contract. Injected data never establishes runtime authority."""
import hashlib
import json
import re
from datetime import datetime, timedelta

IDENTITY = ('tenant_id', 'incident_id', 'impact_incident_id', 'run_id', 'attempt_id')
RECEIPT = ('tenant_id', 'incident_id', 'run_id', 'attempt_id', 'proposal_id', 'ticket_id', 'approval_id')
INTENT = set(RECEIPT) | {'scenario_id', 'mode', 'approval_issuer', 'idempotency_key', 'human_approved', 'execution_allowed', 'effect_allowed'}
AUTHORITIES = ('core', 'twin', 'policy')


def _id(v):
    return isinstance(v, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{2,99}', v) is not None


def _utc(v):
    if not isinstance(v, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z', v):
        raise ValueError('INVALID_UTC')
    return datetime.fromisoformat(v.replace('Z', '+00:00'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def qualify_context(expected, intent, readbacks, policies, *, as_of_utc, source_registry=None):
    """Validate proposed normalized envelopes, not actual server wire formats.

    No network or authority injection can promote this result to runtime PASS.
    Policies map source_id to an explicit nonnegative maximum age in seconds.
    """
    result = {'schema': 'aiops.acme.runtime-context.v1', 'scope': 'RUNTIME_SANDBOX',
              'qualification': 'BLOCK', 'reason': 'INJECTED_READBACKS_NOT_ATTESTED',
              'binding_status': 'UNBOUND', 'runtime_freshness': 'UNKNOWN',
              'runtime_attested': False, 'live_remediation_authorized': False,
              'context': None, 'evidence': []}
    def stop(reason, reject=True):
        return dict(result, qualification='REJECT' if reject else 'BLOCK', reason=reason)
    if not isinstance(expected, dict) or set(expected) != set(IDENTITY) | {'snapshot_id'} or not all(_id(v) for v in expected.values()):
        return stop('IDENTITY_INVALID')
    if expected['tenant_id'] != 'ACME-TEST' or not expected['attempt_id'].startswith('ACME-SIM-') or expected['run_id'].startswith(('SIM-ACME-', 'ACME-SIM-')) or expected['incident_id'] == expected['impact_incident_id']:
        return stop('IDENTITY_INVALID')
    if not isinstance(intent, dict) or set(intent) != INTENT or not all(_id(intent.get(k)) for k in RECEIPT) or any(intent[k] != expected[k] for k in RECEIPT[:4]) or intent['idempotency_key'] != expected['attempt_id']:
        return stop('INTENT_MISMATCH')
    if (intent['scenario_id'], intent['mode'], intent['approval_issuer']) != ('ACME-SAN-PAYMENTS', 'SIMULATION', 'TWIN_ACME_SIMULATED') or any(intent[k] is not False for k in ('human_approved','execution_allowed','effect_allowed')) or not intent['ticket_id'].startswith('SIM-GLPI-') or not intent['approval_id'].startswith('SIM-APP-'):
        return stop('INTENT_MISMATCH')
    if not isinstance(readbacks, dict) or not isinstance(policies, dict) or set(readbacks) - set(AUTHORITIES):
        return stop('AUTHORITY_INVALID')
    try:
        now = _utc(as_of_utc)
    except ValueError:
        return stop('CLOCK_INVALID')
    if source_registry is not None and (not isinstance(source_registry, dict) or set(source_registry) != set(AUTHORITIES)):
        return stop('SOURCE_REGISTRY_INVALID')
    seen = set()
    refs = set()
    evidence = []
    for authority in AUTHORITIES:
        row = readbacks.get(authority)
        if row is None:
            return stop('AUTHORITY_MISSING:' + authority, False)
        keys = {'authority','scope','source_id','source_ref','observed_at','snapshot_id','content_sha256','content'}
        if not isinstance(row, dict) or set(row) != keys or row['authority'] != authority or row['scope'] != 'RUNTIME_SANDBOX':
            return stop('AUTHORITY_INVALID:' + authority)
        if row['snapshot_id'] != expected['snapshot_id']:
            return stop('SNAPSHOT_MISMATCH')
        source = row['source_id']
        if not _id(source) or source in seen or not isinstance(row['source_ref'], str) or not row['source_ref'].strip():
            return stop('PROVENANCE_INVALID')
        if row['source_ref'] in refs:
            return stop('SOURCE_REF_COLLISION')
        refs.add(row['source_ref'])
        if source_registry is not None and source_registry[authority] != source:
            return stop('SOURCE_NOT_REGISTERED:' + authority)
        seen.add(source)
        content = row['content']
        if isinstance(content, dict) and (content.get('scope', 'RUNTIME_SANDBOX') != 'RUNTIME_SANDBOX' or any(content.get(k, False) is not False for k in ('runtime_attested', 'live_remediation_authorized', 'human_approved', 'execution_allowed', 'effect_allowed'))):
            return stop('UNQUALIFIED_CONTENT_CLAIM')
        if not isinstance(content, dict) or any(content.get(k) != expected[k] for k in IDENTITY) or any(content.get(k) != intent[k] for k in RECEIPT) or content.get('idempotency_key') != intent['idempotency_key']:
            return stop('IDENTITY_MISMATCH:' + authority)
        try:
            if digest(content) != row['content_sha256']:
                return stop('DIGEST_MISMATCH')
            age = now - _utc(row['observed_at'])
        except (ValueError, TypeError, OverflowError, RecursionError):
            return stop('PROVENANCE_INVALID')
        if age < timedelta(0):
            return stop('FUTURE_OBSERVATION')
        limit = policies.get(source)
        if type(limit) is not int or limit < 0:
            return stop('FRESHNESS_POLICY_MISSING', False)
        if age.days * 86400 * 1000000 + age.seconds * 1000000 + age.microseconds > limit * 1000000:
            return stop('STALE_OBSERVATION', False)
        evidence.append({k: row[k] for k in keys - {'content'}})
    if source_registry is None:
        return stop('SOURCE_REGISTRY_MISSING', False)
    return dict(result, context=dict(expected), evidence=evidence)


def read_context(expected, intent, readers, policies, *, as_of_utc, source_registry=None):
    """Injected zero-argument consumers only; no HTTP or credentials here."""
    if not isinstance(readers, dict) or set(readers) - set(AUTHORITIES) or any(not callable(v) for v in readers.values()):
        return qualify_context(expected, intent, None, policies, as_of_utc=as_of_utc, source_registry=source_registry)
    readbacks = {}
    for authority in AUTHORITIES:
        reader = readers.get(authority)
        if reader is not None:
            try:
                readbacks[authority] = reader()
            except (TimeoutError, ConnectionError, OSError):
                readbacks[authority] = None
    return qualify_context(expected, intent, readbacks, policies, as_of_utc=as_of_utc, source_registry=source_registry)
