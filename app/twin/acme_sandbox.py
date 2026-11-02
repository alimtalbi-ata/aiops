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
import requests
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from shared.db import db

router = APIRouter()
TENANT, SCENARIO, ISSUER = 'ACME-TEST', 'ACME-SAN-PAYMENTS', 'TWIN_ACME_SIMULATED'
SCHEMA = 'aiops.acme-sandbox-capabilities.v1'
ROOT, PAYMENTS = 'ACME-SAN-FABRIC-A', 'ACME-SVC-PAYMENTS'
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
                or payload.get('approval_issuer') != ISSUER
                or payload.get('issuer_id') != 'twin-acme-test'
                or payload.get('approval_actor') != ISSUER
                or payload.get('approval_kind') != 'SIMULATED'
                or payload.get('approval_status') != 'SIMULATED'
                or payload.get('mode') != 'SIMULATION'
                or payload.get('human_approved') is not False
                or payload.get('execution_allowed') is not False
                or payload.get('effect_allowed') is not False
                or payload.get('live_effects_allowed') is not False
                or payload.get('real_glpi_writes_allowed') is not False
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
        response = requests.get(
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
    if (core.get('attempt_id') != x.attempt_id
            or core.get('tenant_id') != TENANT
            or core.get('incident_id') != x.incident_id
            or core.get('run_id') != x.run_id
            or core.get('ticket_id') != x.ticket_id
            or core.get('proposal_id') != x.proposal_id
            or core.get('ticket_authority') != 'SIMULATED_ONLY'
            or core.get('ticket_status') != 'RESOLVED'
            or core.get('incident_status') != 'RESOLVED'
            or core.get('run_status') != 'RESOLVED'
            or core.get('source') != 'SYNTHETIC_SIMULATOR'
            or core.get('analysis_validated') is not True
            or core.get('critic_validated') is not True
            or type(core.get('evidence_count')) is not int
            or core['evidence_count'] < 2):
        raise HTTPException(503, 'core_sandbox_authority_unqualified')

def sourced_impact():
    with db() as c:
        rows = c.execute("""with recursive down(id,depth) as (
            select %s,0 union select e.target_id,d.depth+1
            from aiops.twin_edges e join down d on e.source_id=d.id where d.depth<8)
            select distinct id from down""", (ROOT,)).fetchall()
        nodes = {r[0] for r in c.execute(
            'select node_id from aiops.twin_nodes where node_id=%s', (ROOT,)).fetchall()}
    affected = sorted({r[0] for r in rows})
    if ROOT not in nodes or PAYMENTS not in affected:
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
    check_core(core_readback(x), x)
    affected = sourced_impact()
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
                'approval_issuer': ISSUER, 'issuer_id': 'twin-acme-test',
                'approval_actor': ISSUER, 'approval_kind': 'SIMULATED',
                'approval_status': 'SIMULATED',
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
        if any(result.get(k) != getattr(x, k)
               for k in ('incident_id', 'run_id', 'ticket_id', 'proposal_id')):
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
