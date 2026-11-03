"""Twin-owned signed sandbox-only approval; never human IdP/GLPI ALLOW.

An immutable, HMAC-attested fact is stored in the existing Twin facts table.
No topology mutation, real GLPI write, LIVE authorization, or host stack change.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
import requests
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from shared.db import db

router = APIRouter()
TENANT, SCENARIO, ISSUER = 'ACME-TEST', 'ACME-SAN-PAYMENTS', 'TWIN_ACME_SIMULATED'
SCHEMA = 'aiops.acme-sandbox-capabilities.v1'
ROOT, PAYMENTS = 'ACME-TEST-SAN-FABRIC-A', 'ACME-TEST-SVC-PAYMENTS'
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{2,99}\Z', re.ASCII)

def enabled():
    key = os.getenv('AIOPS_ACME_TWIN_APPROVAL_KEY', '')
    return (os.getenv('AIOPS_ACME_SANDBOX_ENABLED') == 'true'
            and len(key.encode()) >= 32 and bool(os.getenv('AIOPS_INTERNAL_TOKEN')))

def require_enabled():
    if not enabled():
        raise HTTPException(503, 'sandbox_twin_disabled')

def auth(authorization):
    token = os.getenv('AIOPS_INTERNAL_TOKEN', '')
    supplied = (authorization or '').removeprefix('Bearer ')
    if not token or not supplied or not hmac.compare_digest(token, supplied):
        raise HTTPException(401, 'sandbox_internal_auth_required')

def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()

def sign(data):
    return hmac.new(os.environ['AIOPS_ACME_TWIN_APPROVAL_KEY'].encode(),
                    canonical(data), hashlib.sha256).hexdigest()

def fact_id(attempt):
    return 'FACT-ACME-SIM-' + hashlib.sha256((TENANT + ':' + attempt).encode()).hexdigest()[:32].upper()

def approval_id(attempt):
    return 'SIM-APP-' + hashlib.sha256((TENANT + ':' + attempt).encode()).hexdigest()[:24].upper()

def canonical_source_ids(attempt):
    """Independently derive Core's seven sandbox SOURCE keys, in ordinal order."""
    return ['SYN-EVT-' + hashlib.sha256(
        (TENANT + ':' + attempt + ':' + str(index)).encode()
    ).hexdigest()[:20].upper() for index in range(1, 8)]

def utc(value):
    try:
        result = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        raise HTTPException(503, 'sandbox_approval_time_invalid') from None
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise HTTPException(503, 'sandbox_approval_time_invalid')
    return result.astimezone(timezone.utc)

def verified_record(value, *, attempt_id, now=None):
    try:
        doc = json.loads(value) if isinstance(value, str) else value
        payload, signature = doc['payload'], doc['signature']
        if not isinstance(payload, dict) or not isinstance(signature, str):
            raise ValueError('shape')
        if not hmac.compare_digest(sign(payload), signature):
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
        now = now or datetime.now(timezone.utc)
        if (issued > now + timedelta(seconds=30) or expires <= now
                or expires <= issued or expires - issued > timedelta(minutes=5)):
            raise ValueError('expired')
        return payload
    except (KeyError, ValueError, TypeError, AttributeError):
        raise HTTPException(503, 'sandbox_approval_unqualified') from None

class ApprovalIntent(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    attempt_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{2,99}$')
    tenant_id: str
    scenario_id: str
    mode: str
    approval_issuer: str
    incident_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{2,99}$')
    run_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{2,99}$')
    ticket_id: str = Field(pattern=r'^SIM-GLPI-[A-Za-z0-9_-]{3,91}$')
    proposal_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{2,99}$')
    idempotency_key: str
    live_effects_allowed: bool

def validate_intent(x):
    if (x.tenant_id != TENANT or x.scenario_id != SCENARIO
            or x.mode != 'SIMULATION' or x.approval_issuer != ISSUER
            or x.idempotency_key != x.attempt_id or x.live_effects_allowed is not False):
        raise HTTPException(403, 'sandbox_intent_denied')

def core_readback(x):
    """Independently authenticated Core read; never caller-supplied evidence."""
    base = os.getenv('CORE_URL', 'http://aiops2-core:810').rstrip('/')
    try:
        target = urlsplit(base)
    except ValueError:
        raise HTTPException(503, 'independent_core_url_invalid') from None
    # Do not forward the internal bearer token to an arbitrary configured origin.
    # Match the existing Compose Core DNS names and the disposable local test origin.
    if (target.scheme not in ('http', 'https')
            or target.netloc not in ('aiops2-core:810', 'aiops2-rebuild-core:810',
                                     'localhost:810', '127.0.0.1:810')
            or target.username or target.password or target.path
            or target.query or target.fragment):
        raise HTTPException(503, 'independent_core_url_invalid')
    try:
        # Fixed Core host/port alone is insufficient when requests inherits HTTP(S)_PROXY.
        # Never expose the internal bearer to an environment-configured proxy.
        with requests.Session() as session:
            session.trust_env = False
            response = session.get(
                base + '/api/sandbox/acme/e2e/' + x.attempt_id,
                headers={'Authorization': 'Bearer ' + os.environ['AIOPS_INTERNAL_TOKEN']},
                timeout=5, allow_redirects=False)
        if response.status_code != 200 or len(response.content) > 32768:
            raise ValueError('unavailable')
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError('shape')
        return result
    except (requests.RequestException, ValueError):
        raise HTTPException(503, 'independent_core_readback_unavailable') from None

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


def check_core_fence(x):
    """Two independent Core GETs must agree before any Twin approval write."""
    first = core_readback(x)
    fingerprint = check_core(first, x)
    second = core_readback(x)
    if check_core(second, x) != fingerprint:
        raise HTTPException(503, 'core_prepared_snapshot_changed')
    return fingerprint

def sourced_impact():
    with db() as c:
        rows = c.execute("""with recursive down(id,depth) as (
            select %s,0 union select e.target_id,d.depth+1
            from aiops.twin_edges e join down d on e.source_id=d.id where d.depth<8)
            select distinct d.id,n.site from down d
            left join aiops.twin_nodes n on n.node_id=d.id""", (ROOT,)).fetchall()
    affected = sorted({node_id for node_id, site in rows})
    # A synthetic Twin approval may not inherit a path into live CMDB nodes.
    # Missing or mixed provenance is UNKNOWN/503, never fabricated impact.
    if (ROOT not in affected or PAYMENTS not in affected
            or any(site != 'ACME-TEST-SIMULATION' for _, site in rows)):
        raise HTTPException(503, 'twin_sourced_payments_path_unavailable')
    return affected

@router.get('/api/sandbox/acme/capabilities')
def capabilities():
    require_enabled()
    sourced_impact()
    return {'schema': SCHEMA, 'component': 'twin', 'tenant_id': TENANT,
            'mode': 'SIMULATION', 'isolated': True, 'approval_issuer': ISSUER,
            'human_approval_claimed': False, 'live_effects_allowed': False,
            'real_glpi_writes_allowed': False}

@router.post('/api/sandbox/acme/approvals')
def issue_approval(x: ApprovalIntent, authorization: str | None = Header(default=None)):
    auth(authorization)
    require_enabled()
    validate_intent(x)
    core_fingerprint = check_core_fence(x)
    affected = sourced_impact()
    # A third authenticated GET closes the graph-read-to-approval-write race.
    if check_core(core_readback(x), x) != core_fingerprint:
        raise HTTPException(503, 'core_prepared_snapshot_changed')
    fid = fact_id(x.attempt_id)
    with db() as c:
        existing = c.execute('select value from aiops.twin_facts where fact_id=%s', (fid,)).fetchone()
        if existing:
            result = verified_record(existing[0], attempt_id=x.attempt_id)
        else:
            now = datetime.now(timezone.utc)
            payload = {
                'attempt_id': x.attempt_id, 'tenant_id': TENANT,
                'scenario_id': SCENARIO, 'mode': 'SIMULATION',
                'incident_id': x.incident_id, 'run_id': x.run_id,
                'ticket_id': x.ticket_id, 'proposal_id': x.proposal_id,
                'approval_id': approval_id(x.attempt_id),
                'idempotency_key': x.attempt_id,
                'core_request_sha256': core_fingerprint[0],
                'core_source_event_ids': list(core_fingerprint[1]),
                'approval_issuer': ISSUER, 'issuer_id': 'twin-acme-test',
                'approval_actor': ISSUER, 'approval_kind': 'SIMULATED',
                'approval_status': 'SIMULATED',
                'approval_phase': 'PRE_RESOLUTION',
                'core_status_at_issuance': 'PREPARED',
                'resolution_verified': False,
                'post_resolution_readback_required': True,
                'approval_nonce': 'SIMNONCE-' + secrets.token_hex(16).upper(),
                'issued_at': now.isoformat(),
                'expires_at': (now + timedelta(minutes=4)).isoformat(),
                'impact_root': ROOT, 'impacted_cis': affected,
                'human_approved': False, 'execution_allowed': False,
                'effect_allowed': False, 'live_effects_allowed': False,
                'real_glpi_writes_allowed': False}
            record = {'payload': payload, 'signature': sign(payload)}
            c.execute("""insert into aiops.twin_facts
                (fact_id,node_id,attribute,value,valid_from,confidence)
                values(%s,%s,'sandbox_simulated_approval',%s,now(),1.0)
                on conflict(fact_id) do nothing""", (fid, ROOT, json.dumps(record)))
            stored = c.execute('select value from aiops.twin_facts where fact_id=%s', (fid,)).fetchone()
            if not stored:
                raise HTTPException(503, 'sandbox_approval_persistence_unavailable')
            result = verified_record(stored[0], attempt_id=x.attempt_id)
        if (any(result.get(k) != getattr(x, k)
                for k in ('incident_id', 'run_id', 'ticket_id', 'proposal_id'))
                or result.get('core_request_sha256') != core_fingerprint[0]
                or result.get('core_source_event_ids') != list(core_fingerprint[1])):
            raise HTTPException(409, 'sandbox_attempt_rebinding_denied')
        return result

@router.get('/api/sandbox/acme/e2e/{attempt_id}')
def approval_readback(attempt_id: str, authorization: str | None = Header(default=None)):
    auth(authorization)
    require_enabled()
    if not ID.fullmatch(attempt_id):
        raise HTTPException(422, 'invalid_attempt_id')
    with db() as c:
        row = c.execute('select value from aiops.twin_facts where fact_id=%s',
                        (fact_id(attempt_id),)).fetchone()
    if not row:
        raise HTTPException(404, 'sandbox_approval_not_found')
    return verified_record(row[0], attempt_id=attempt_id)
