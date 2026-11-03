"""Fail-closed ACME SAN->Payments sandbox coordinator; no LIVE or GLPI effects."""
import hashlib
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
# Service-specific Compose/local origins; never forward internal bearer to a foreign host/port.
ALLOWED_ORIGINS = {
    component: frozenset((f'aiops2-{component}:{port}',
                          f'aiops2-rebuild-{component}:{port}',
                          f'localhost:{port}', f'127.0.0.1:{port}'))
    for component, port in (('core', 810), ('twin', 811),
                            ('policy', 813), ('worker', 815))
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
    try:
        parsed = urlsplit(base)
    except ValueError:
        raise HTTPException(503, 'sandbox_service_url_invalid') from None
    if (parsed.scheme not in ('http', 'https')
            or parsed.netloc not in ALLOWED_ORIGINS[component]
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
        raise HTTPException(503, 'sandbox_service_url_invalid')
    try:
        # Keep the internal bearer off HTTP(S)/ALL_PROXY inherited from the host.
        with requests.Session() as session:
            session.trust_env = False
            response = session.request(
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


def canonical_source_ids(attempt_id):
    """Independently derive Core's ordered synthetic SOURCE IDs, never trust the readback order."""
    return ['SYN-EVT-' + hashlib.sha256(
        (TENANT + ':' + attempt_id + ':' + str(index)).encode()
    ).hexdigest()[:20].upper() for index in range(1, 8)]


def prepared_core(value, x, ids=None):
    """Core is the sole state authority; never approve a pre-resolved Run."""
    bound(value, x, ids)
    event_ids = value.get('source_event_ids')
    if (value.get('incident_status') != 'PREPARED'
            or value.get('run_status') != 'PREPARED'
            or value.get('ticket_status') != 'PREPARED'
            or value.get('ticket_authority') != 'SIMULATED_ONLY'
            or value.get('approval_issuer') != ISSUER
            or value.get('source') != 'SYNTHETIC_SIMULATOR'
            or type(value.get('source_event_count')) is not int
            or value['source_event_count'] != 7
            or value.get('source_hashes_qualified') is not True
            or type(event_ids) is not list or len(event_ids) != 7
            or event_ids != canonical_source_ids(x.attempt_id)
            or any(not valid_id(v) for v in event_ids)
            or type(value.get('request_sha256')) is not str
            or re.fullmatch(r'[0-9a-f]{64}', value['request_sha256']) is None
            or value.get('analysis_validated') is not True
            or value.get('critic_validated') is not True
            or type(value.get('evidence_count')) is not int
            or value['evidence_count'] < 2
            or value.get('human_approved') is not False
            or value.get('execution_allowed') is not False
            or value.get('effect_allowed') is not False
            or value.get('live_effects_allowed') is not False
            or value.get('real_glpi_writes_allowed') is not False):
        raise HTTPException(503, 'sandbox_core_not_prepared')
    return value['request_sha256'], tuple(event_ids)

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
    fingerprint = prepared_core(core, x, ids)
    # Core owns incident/Run/ticket/proposal. Only Twin can issue the approval.
    twin = remote('twin', '/api/sandbox/acme/approvals', 'POST', {**request, **ids})
    bound(twin, x, ids)
    aid = twin.get('approval_id')
    if (not valid_id(aid) or not aid.startswith('SIM-APP-')
            or twin.get('approval_issuer') != ISSUER
            or twin.get('approval_kind') != 'SIMULATED'
            or twin.get('approval_phase') != 'PRE_RESOLUTION'
            or twin.get('core_status_at_issuance') != 'PREPARED'
            or twin.get('resolution_verified') is not False
            or twin.get('post_resolution_readback_required') is not True
            or twin.get('issuer_id') != 'twin-acme-test'
            or twin.get('core_request_sha256') != fingerprint[0]
            or twin.get('core_source_event_ids') != list(fingerprint[1])
            or twin.get('human_approved') is not False
            or twin.get('execution_allowed') is not False
            or twin.get('effect_allowed') is not False
            or twin.get('live_effects_allowed') is not False
            or twin.get('real_glpi_writes_allowed') is not False):
        raise HTTPException(503, 'sandbox_twin_approval_unqualified')
    ids['approval_id'] = aid
    # Verify independent Twin GET rather than trusting the POST body.
    readback = remote('twin', '/api/sandbox/acme/e2e/' + x.attempt_id)
    bound(readback, x, ids)
    if (readback.get('approval_nonce') != twin.get('approval_nonce')
            or readback.get('core_request_sha256') != fingerprint[0]
            or readback.get('core_source_event_ids') != list(fingerprint[1])
            or readback.get('approval_issuer') != ISSUER
            or readback.get('approval_kind') != 'SIMULATED'
            or readback.get('approval_phase') != 'PRE_RESOLUTION'
            or readback.get('core_status_at_issuance') != 'PREPARED'
            or readback.get('issuer_id') != 'twin-acme-test'
            or readback.get('resolution_verified') is not False
            or readback.get('post_resolution_readback_required') is not True
            or readback.get('human_approved') is not False
            or readback.get('execution_allowed') is not False
            or readback.get('effect_allowed') is not False
            or readback.get('live_effects_allowed') is not False
            or readback.get('real_glpi_writes_allowed') is not False):
        raise HTTPException(503, 'sandbox_twin_readback_unqualified')
    policy = remote('policy', '/api/sandbox/acme/e2e', 'POST', {**request, **ids})
    bound(policy, x, ids)
    if (policy.get('decision') != 'SIMULATE'
            or policy.get('human_approved') is not False
            or policy.get('live_effects_allowed') is not False):
        raise HTTPException(503, 'sandbox_policy_unqualified')
    # Re-read Core before Worker: Twin/Policy may never race a resolution.
    before_worker = remote('core', '/api/sandbox/acme/e2e/' + x.attempt_id)
    # Core must not mint Twin's approval_id; compare only Core-owned identities.
    core_ids = {k: v for k, v in ids.items() if k != 'approval_id'}
    if prepared_core(before_worker, x, core_ids) != fingerprint:
        raise HTTPException(503, 'sandbox_core_snapshot_changed')
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
