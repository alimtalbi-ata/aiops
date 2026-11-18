"""ACME-TEST Policy SIMULATE-only readback; no human GLPI or LIVE authority.

RG-ACME-07: new SIMULATE decisions require Core PREPARED, never RESOLVED.
A new decision requires PREPARED. Historical RESOLVED GET requires Core's
independently persisted terminal ticket and Worker receipt digest; it never
issues a fresh decision or authorizes human/LIVE effects.
"""
import hashlib
import hmac
import json
import os
import re
from urllib.parse import urlsplit
from fastapi import HTTPException
from fastapi.responses import JSONResponse

TENANT = 'ACME-TEST'
ISSUER = 'TWIN_ACME_SIMULATED'
SCENARIO = 'ACME-SAN-PAYMENTS'
ID = re.compile(r'ACME-SIM-[A-Za-z0-9_-]{8,80}\Z', re.ASCII)
NO_STORE = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}

def guard():
    raise HTTPException(503, 'int09_persistent_candidate_disabled')

def auth(authorization):
    raise HTTPException(503, 'int09_persistent_candidate_disabled')

def fetch_component(component, attempt):
    raise HTTPException(503, 'int09_persistent_candidate_disabled')

def qualify(attempt, core, twin, *, historical=False):
    expected_status = 'RESOLVED' if historical else 'PREPARED'
    ids = ('incident_id', 'run_id', 'ticket_id', 'proposal_id')
    if (any(doc.get('attempt_id') != attempt or doc.get('tenant_id') != TENANT
            for doc in (core, twin))
            or any(not isinstance(core.get(k), str) or not core[k]
                   or core[k] != twin.get(k) for k in ids)
            or not core['ticket_id'].startswith('SIM-GLPI-')
            or core.get('incident_status') != expected_status
            or core.get('run_status') != core.get('incident_status')
            or core.get('ticket_status') != expected_status
            or core.get('ticket_authority') != 'SIMULATED_ONLY'
            or core.get('glpi_mode') != 'SIMULATED_ONLY'
            or core.get('source_event_count') != 7
            or core.get('source_hashes_qualified') is not True
            or core.get('analysis_validated') is not True
            or core.get('critic_validated') is not True
            or type(core.get('evidence_count')) is not int
            or core['evidence_count'] < 2
            or twin.get('approval_issuer') != ISSUER
            or twin.get('issuer_id') != 'twin-acme-test'
            or twin.get('approval_kind') != 'SIMULATED'
            or twin.get('approval_status') != 'SIMULATED'
            or twin.get('approval_phase') != 'PRE_RESOLUTION'
            or twin.get('core_status_at_issuance') != 'PREPARED'
            or twin.get('core_request_sha256') != core.get('request_sha256')
            or twin.get('core_source_event_ids') != core.get('source_event_ids')
            or not isinstance(twin.get('approval_id'), str)
            or not twin['approval_id'].startswith('SIM-APP-')
            or any(doc.get(k) is not False for doc in (core, twin)
                   for k in ('human_approved', 'execution_allowed',
                             'effect_allowed', 'live_effects_allowed',
                             'real_glpi_writes_allowed'))):
        raise HTTPException(503, 'sandbox_policy_join_unqualified')
    if historical:
        # RG-ACME-24: read-only replay of a persisted simulated decision,
        # never an approval or new Policy evaluation after Core RESOLVED.
        worker_sha = core.get('worker_receipt_sha256')
        ticket_sha = core.get('terminal_ticket_sha256')
        if (core.get('source') != 'SYNTHETIC_SIMULATOR'
                or core.get('approval_id') != twin.get('approval_id')
                or core.get('worker_receipt_verified') is not True
                or core.get('terminal_ticket_receipt_verified') is not True
                or core.get('resolution_after_worker_receipt') is not True
                or core.get('approval_fresh_at_resolution') is not True
                or core.get('approval_nonce_consumed') is not True
                or core.get('approval_nonce_revoked') is not False
                or not isinstance(worker_sha, str)
                or not re.fullmatch(r'[a-f0-9]{64}', worker_sha)
                or not isinstance(ticket_sha, str)
                or not re.fullmatch(r'[a-f0-9]{64}', ticket_sha)):
            raise HTTPException(503, 'sandbox_historical_receipts_unqualified')
        binding = {
            'schema': 'aiops.portal.sim-glpi-ticket-digest.v1',
            'tenant_id': TENANT, 'attempt_id': attempt,
            'incident_id': core['incident_id'], 'run_id': core['run_id'],
            'ticket_id': core['ticket_id'], 'ticket_status': 'RESOLVED',
            'core_request_sha256': core.get('request_sha256'),
            'worker_receipt_sha256': worker_sha}
        expected_sha = hashlib.sha256(json.dumps(
            binding, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if not hmac.compare_digest(ticket_sha, expected_sha):
            raise HTTPException(503, 'sandbox_historical_ticket_digest_mismatch')
    return ids

def read(attempt, *, allow_historical=True):
    if not ID.fullmatch(attempt):
        raise HTTPException(422, 'invalid_sandbox_attempt')
    core = fetch_component('core', attempt)
    twin = fetch_component('twin', attempt)
    historical = core.get('incident_status') == 'RESOLVED'
    if historical and not allow_historical:
        raise HTTPException(503, 'sandbox_new_decision_after_resolution_denied')
    qualify(attempt, core, twin, historical=historical)
    if not historical:
        # Only PREPARED can evaluate a new SIMULATE decision.
        from policy.main import Decision, evaluate
        result = evaluate(Decision(
            mode='DEMO', command='RESOLVE', severity='P2', confidence=1.0,
            evidence_count=core['evidence_count'], critic_validated=True,
            redundancy_ok=True, evidence_fresh=True, human_approved=False))
        if result.get('state') != 'PASS' or result.get('decision') != 'SIMULATE':
            raise HTTPException(503, 'sandbox_policy_not_simulate')
    return {'schema': 'aiops.policy-acme-simulated.v1',
            'attempt_id': attempt, 'tenant_id': TENANT,
            'incident_id': core['incident_id'], 'run_id': core['run_id'],
            'ticket_id': core['ticket_id'], 'proposal_id': core['proposal_id'],
            'approval_id': twin['approval_id'], 'approval_issuer': ISSUER,
            'approval_kind': 'SIMULATED', 'mode': 'SIMULATION',
            'decision': 'SIMULATE', 'state': 'PASS',
            'historical_readback': historical, 'new_approval_issued': False,
            'human_approved': False, 'human_approval_claimed': False,
            'execution_allowed': False, 'effect_allowed': False,
            'live_effects_allowed': False, 'real_glpi_writes_allowed': False}

def capabilities():
    guard()
    return {'schema': 'aiops.acme-sandbox-capabilities.v1',
            'component': 'policy', 'tenant_id': TENANT, 'mode': 'SIMULATION',
            'isolated': True, 'approval_issuer': ISSUER,
            'human_approval_claimed': False, 'live_effects_allowed': False,
            'real_glpi_writes_allowed': False}

def readback(attempt_id: str, authorization: str | None = None):
    guard()
    auth(authorization)
    return JSONResponse(read(attempt_id), headers=NO_STORE)

def start(intent: dict, authorization: str | None = None):
    guard()
    auth(authorization)
    keys = {'attempt_id', 'tenant_id', 'scenario_id', 'mode', 'approval_issuer',
            'idempotency_key', 'live_effects_allowed', 'incident_id', 'run_id',
            'ticket_id', 'proposal_id', 'approval_id'}
    if (type(intent) is not dict or set(intent) != keys
            or type(intent.get('attempt_id')) is not str
            or not ID.fullmatch(intent['attempt_id'])
            or intent.get('tenant_id') != TENANT
            or intent.get('scenario_id') != SCENARIO
            or intent.get('mode') != 'SIMULATION'
            or intent.get('approval_issuer') != ISSUER
            or intent.get('idempotency_key') != intent['attempt_id']
            or intent.get('live_effects_allowed') is not False):
        raise HTTPException(403, 'sandbox_policy_intent_denied')
    result = read(intent['attempt_id'], allow_historical=False)
    if any(intent[k] != result[k] for k in
           ('incident_id', 'run_id', 'ticket_id', 'proposal_id', 'approval_id')):
        raise HTTPException(503, 'sandbox_policy_intent_binding_mismatch')
    return JSONResponse(result, headers=NO_STORE)


def db():
    raise HTTPException(503, 'int09_persistence_not_authorized')
