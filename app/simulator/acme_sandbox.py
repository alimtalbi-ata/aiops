"""Fail-closed ACME SAN->Payments sandbox coordinator; no LIVE or GLPI effects."""
import hmac
import os
import re
from urllib.parse import urlsplit
import requests
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter()
TENANT, SCENARIO, ISSUER = 'ACME-TEST', 'ACME-SAN-PAYMENTS', 'TWIN_ACME_SIMULATED'
SCHEMA = 'aiops.acme-sandbox-capabilities.v1'
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{2,99}\Z', re.ASCII)
SERVICES = {
    'core': ('CORE_URL', 'http://aiops2-core:810'),
    'twin': ('TWIN_URL', 'http://aiops2-twin:811'),
    'policy': ('POLICY_URL', 'http://aiops2-policy:813'),
    'worker': ('WORKER_URL', 'http://aiops2-worker:815'),
}

def enabled():
    return os.getenv('AIOPS_ACME_SANDBOX_ENABLED') == 'true' and bool(os.getenv('AIOPS_INTERNAL_TOKEN'))

def require_enabled():
    if not enabled():
        raise HTTPException(503, 'sandbox_simulator_disabled')

def auth(authorization):
    token = os.getenv('AIOPS_INTERNAL_TOKEN', '')
    supplied = (authorization or '').removeprefix('Bearer ')
    if not token or not supplied or not hmac.compare_digest(token, supplied):
        raise HTTPException(401, 'sandbox_internal_auth_required')

def remote(component, path, method='GET', payload=None):
    """Fixed service/path allowlist; bounded JSON, no redirects, no caller-supplied URLs."""
    if component not in SERVICES or not path.startswith('/api/sandbox/acme/'):
        raise HTTPException(503, 'sandbox_target_denied')
    env, default = SERVICES[component]
    base = os.getenv(env, default).rstrip('/')
    parsed = urlsplit(base)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
        raise HTTPException(503, 'sandbox_service_url_invalid')
    try:
        response = requests.request(
            method, base + path,
            headers={'Authorization': 'Bearer ' + os.environ['AIOPS_INTERNAL_TOKEN'],
                     'Accept': 'application/json'},
            json=payload if method == 'POST' else None,
            timeout=5, allow_redirects=False)
        if response.status_code != 200 or len(response.content) > 32768:
            raise ValueError('unqualified')
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError('shape')
        return data
    except (requests.RequestException, ValueError):
        raise HTTPException(503, 'sandbox_' + component + '_unavailable') from None

def qualified(component, value):
    return (type(value) is dict and value.get('schema') == SCHEMA
            and value.get('component') == component and value.get('tenant_id') == TENANT
            and value.get('mode') == 'SIMULATION' and value.get('isolated') is True
            and value.get('approval_issuer') == ISSUER
            and value.get('human_approval_claimed') is False
            and value.get('live_effects_allowed') is False
            and value.get('real_glpi_writes_allowed') is False)

class SandboxRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    attempt_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{2,99}$')
    tenant_id: str
    scenario_id: str
    mode: str
    approval_issuer: str
    idempotency_key: str
    live_effects_allowed: bool

def validate_request(x):
    if (x.tenant_id != TENANT or x.scenario_id != SCENARIO
            or x.mode != 'SIMULATION' or x.approval_issuer != ISSUER
            or x.idempotency_key != x.attempt_id or x.live_effects_allowed is not False):
        raise HTTPException(403, 'sandbox_request_denied')

def bound(value, request, ids=None):
    if (type(value) is not dict or value.get('attempt_id') != request.attempt_id
            or value.get('tenant_id') != TENANT):
        raise HTTPException(503, 'sandbox_cross_tenant_or_attempt')
    if ids and any(value.get(k) != v for k, v in ids.items()):
        raise HTTPException(503, 'sandbox_cross_run_or_identity')

def valid_id(value):
    return type(value) is str and ID.fullmatch(value) is not None

@router.get('/api/sandbox/acme/capabilities')
def capabilities():
    require_enabled()
    return {'schema': SCHEMA, 'component': 'simulator', 'tenant_id': TENANT,
            'mode': 'SIMULATION', 'isolated': True, 'approval_issuer': ISSUER,
            'human_approval_claimed': False, 'live_effects_allowed': False,
            'real_glpi_writes_allowed': False}

@router.post('/api/sandbox/acme/e2e')
def start(x: SandboxRequest, authorization: str | None = Header(default=None)):
    auth(authorization)
    require_enabled()
    validate_request(x)
    # Every independent authority must opt into the same isolated sandbox BEFORE any POST.
    for component in SERVICES:
        if not qualified(component, remote(component, '/api/sandbox/acme/capabilities')):
            raise HTTPException(503, 'sandbox_capability_unqualified_' + component)
    request = x.model_dump()
    core = remote('core', '/api/sandbox/acme/e2e', 'POST', request)
    bound(core, x)
    ids = {k: core.get(k) for k in ('incident_id', 'run_id', 'ticket_id', 'proposal_id')}
    if (not all(valid_id(v) for v in ids.values())
            or not ids['ticket_id'].startswith('SIM-GLPI-')
            or core.get('glpi_mode') != 'SIMULATED_ONLY'
            or core.get('approval_id') is not None):
        raise HTTPException(503, 'sandbox_core_start_unqualified')
    # Core owns incident/Run/ticket/proposal. Only Twin can issue the approval.
    twin = remote('twin', '/api/sandbox/acme/approvals', 'POST', {**request, **ids})
    bound(twin, x, ids)
    aid = twin.get('approval_id')
    if (not valid_id(aid) or not aid.startswith('SIM-APP-')
            or twin.get('approval_issuer') != ISSUER
            or twin.get('approval_kind') != 'SIMULATED'
            or twin.get('human_approved') is not False
            or twin.get('live_effects_allowed') is not False):
        raise HTTPException(503, 'sandbox_twin_approval_unqualified')
    ids['approval_id'] = aid
    # Verify independent Twin GET rather than trusting the POST body.
    readback = remote('twin', '/api/sandbox/acme/e2e/' + x.attempt_id)
    bound(readback, x, ids)
    if (readback.get('approval_nonce') != twin.get('approval_nonce')
            or readback.get('approval_issuer') != ISSUER
            or readback.get('approval_kind') != 'SIMULATED'):
        raise HTTPException(503, 'sandbox_twin_readback_unqualified')
    policy = remote('policy', '/api/sandbox/acme/e2e', 'POST', {**request, **ids})
    bound(policy, x, ids)
    if (policy.get('decision') != 'SIMULATE'
            or policy.get('human_approved') is not False
            or policy.get('live_effects_allowed') is not False):
        raise HTTPException(503, 'sandbox_policy_unqualified')
    # Worker #348 requires exactly its 14 intent keys, and returns PENDING
    # while Temporal independently validates Core/Twin/Policy. The Debian
    # runner, not this POST response, qualifies the final no-effect GET.
    worker_intent = {
        'attempt_id': x.attempt_id, 'tenant_id': TENANT,
        'scenario_id': SCENARIO, 'mode': 'SIMULATION',
        'approval_issuer': ISSUER, **ids, 'idempotency_key': x.attempt_id,
        'human_approved': False, 'execution_allowed': False,
        'effect_allowed': False,
    }
    worker = remote('worker', '/api/sandbox/acme/e2e', 'POST', worker_intent)
    if (worker.get('attempt_id') != x.attempt_id
            or worker.get('effect_allowed') is not False
            or not valid_id(worker.get('workflow_id'))
            or not (worker.get('status') == 'PENDING_INDEPENDENT_READBACK'
                    or worker.get('idempotent') is True)):
        raise HTTPException(503, 'sandbox_worker_start_unqualified')
    return {**ids, 'attempt_id': x.attempt_id, 'tenant_id': TENANT,
            'scenario_id': SCENARIO, 'mode': 'SIMULATION',
            'glpi_mode': 'SIMULATED_ONLY', 'approval_issuer': ISSUER,
            'human_approval_claimed': False, 'live_effects_allowed': False,
            'real_glpi_writes_allowed': False}
