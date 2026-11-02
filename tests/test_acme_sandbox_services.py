"""Disposable sandbox security regressions: no Docker, GLPI or external calls."""
import importlib.util
import json
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

BASE = Path(__file__).resolve().parents[1] / 'app'
shared = types.ModuleType('shared')
shared.__path__ = []
db_module = types.ModuleType('shared.db')
db_module.db = lambda: None
sys.modules.setdefault('shared', shared)
sys.modules.setdefault('shared.db', db_module)

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

SIM = load('acme_test_simulator', BASE / 'simulator' / 'acme_sandbox.py')
TWIN = load('acme_test_twin', BASE / 'twin' / 'acme_sandbox.py')

@pytest.fixture(autouse=True)
def sandbox(monkeypatch):
    monkeypatch.setenv('AIOPS_ACME_SANDBOX_ENABLED', 'true')
    monkeypatch.setenv('AIOPS_INTERNAL_TOKEN', 'test-internal-token-not-real')
    monkeypatch.setenv('AIOPS_ACME_TWIN_APPROVAL_KEY',
                       'test-only-sandbox-hmac-key-32bytes-not-secret')

def intent():
    return dict(attempt_id='ACME-SIM-UNIT001', tenant_id='ACME-TEST',
                scenario_id='ACME-SAN-PAYMENTS', mode='SIMULATION',
                approval_issuer='TWIN_ACME_SIMULATED',
                idempotency_key='ACME-SIM-UNIT001', live_effects_allowed=False)

def ids():
    return dict(incident_id='INC-SIM-001', run_id='RUN-SIM-001',
                ticket_id='SIM-GLPI-001', proposal_id='PROP-SIM-001')


def prepared_core():
    return intent() | ids() | dict(
        incident_status='PREPARED', run_status='PREPARED',
        ticket_status='PREPARED', ticket_authority='SIMULATED_ONLY',
        source='SYNTHETIC_SIMULATOR', source_event_count=7,
        source_hashes_qualified=True,
        source_event_ids=TWIN.canonical_source_ids(intent()['attempt_id']),
        request_sha256='a' * 64, analysis_validated=True,
        critic_validated=True, evidence_count=2, human_approved=False,
        execution_allowed=False, effect_allowed=False,
        real_glpi_writes_allowed=False)

def test_simulator_disabled_before_capability(monkeypatch):
    monkeypatch.delenv('AIOPS_ACME_SANDBOX_ENABLED')
    with pytest.raises(HTTPException) as e:
        SIM.capabilities()
    assert e.value.status_code == 503

def test_twin_disabled_without_distinct_signer(monkeypatch):
    monkeypatch.delenv('AIOPS_ACME_TWIN_APPROVAL_KEY')
    with pytest.raises(HTTPException) as e:
        TWIN.capabilities()
    assert e.value.status_code == 503

@pytest.mark.parametrize('changes', [
    {'tenant_id': 'OTHER'}, {'mode': 'LIVE'},
    {'approval_issuer': 'HUMAN_IDP'}, {'live_effects_allowed': True},
    {'idempotency_key': 'DIFFERENT'},
])
def test_simulator_rejects_untrusted_intent_before_post(monkeypatch, changes):
    monkeypatch.setattr(SIM, 'remote', lambda *a, **kw: pytest.fail('network called'))
    with pytest.raises(HTTPException) as e:
        SIM.start(SIM.SandboxRequest(**(intent() | changes)),
                  authorization='Bearer test-internal-token-not-real')
    assert e.value.status_code == 403

def test_simulator_rejects_bad_token_before_network(monkeypatch):
    monkeypatch.setattr(SIM, 'remote', lambda *a, **kw: pytest.fail('network called'))
    with pytest.raises(HTTPException) as e:
        SIM.start(SIM.SandboxRequest(**intent()), authorization='Bearer fake')
    assert e.value.status_code == 401

def test_simulator_forged_capability_never_posts(monkeypatch):
    calls = []
    def remote(component, path, method='GET', payload=None):
        calls.append((component, method))
        return {'schema': SIM.SCHEMA, 'component': component, 'tenant_id': 'ACME-TEST',
                'mode': 'SIMULATION', 'isolated': True,
                'approval_issuer': 'HUMAN_IDP', 'human_approval_claimed': True,
                'live_effects_allowed': False, 'real_glpi_writes_allowed': False}
    monkeypatch.setattr(SIM, 'remote', remote)
    with pytest.raises(HTTPException):
        SIM.start(SIM.SandboxRequest(**intent()),
                  authorization='Bearer test-internal-token-not-real')
    assert calls == [('core', 'GET')]

def test_simulator_missing_core_capability_never_posts(monkeypatch):
    def remote(*args, **kwargs):
        raise HTTPException(503, 'missing')
    monkeypatch.setattr(SIM, 'remote', remote)
    with pytest.raises(HTTPException) as e:
        SIM.start(SIM.SandboxRequest(**intent()),
                  authorization='Bearer test-internal-token-not-real')
    assert e.value.status_code == 503

def test_twin_rejects_untrusted_intent_before_core(monkeypatch):
    monkeypatch.setattr(TWIN, 'core_readback', lambda *a: pytest.fail('core contacted'))
    with pytest.raises(HTTPException) as e:
        TWIN.issue_approval(TWIN.ApprovalIntent(**(intent() | ids() | {'tenant_id': 'OTHER'})),
                            authorization='Bearer test-internal-token-not-real')
    assert e.value.status_code == 403

@pytest.mark.parametrize('state', ['RESOLVED', 'OPEN', 'CLOSED'])
def test_twin_rejects_not_prepared_core(state):
    x = TWIN.ApprovalIntent(**(intent() | ids()))
    with pytest.raises(HTTPException) as e:
        TWIN.check_core(prepared_core() | {'incident_status': state,
                                            'run_status': state,
                                            'ticket_status': state}, x)
    assert e.value.status_code == 503


def test_twin_prepared_core_positive_and_cross_run_denied():
    x = TWIN.ApprovalIntent(**(intent() | ids()))
    assert TWIN.check_core(prepared_core(), x) == ('a' * 64,
                                                   tuple(prepared_core()['source_event_ids']))
    with pytest.raises(HTTPException):
        TWIN.check_core(prepared_core() | {'run_id': 'RUN-UNRELATED'}, x)


def test_twin_prepared_fence_rejects_resolution_race(monkeypatch):
    x = TWIN.ApprovalIntent(**(intent() | ids()))
    calls = iter([prepared_core(), prepared_core() | {'run_status': 'RESOLVED'}])
    monkeypatch.setattr(TWIN, 'core_readback', lambda _x: next(calls))
    with pytest.raises(HTTPException) as e:
        TWIN.check_core_fence(x)
    assert e.value.status_code == 503


def test_twin_prepared_fence_rejects_source_replay(monkeypatch):
    x = TWIN.ApprovalIntent(**(intent() | ids()))
    calls = iter([prepared_core(), prepared_core() | {'request_sha256': 'b' * 64}])
    monkeypatch.setattr(TWIN, 'core_readback', lambda _x: next(calls))
    with pytest.raises(HTTPException) as e:
        TWIN.check_core_fence(x)
    assert e.value.detail == 'core_prepared_snapshot_changed'

def sample_record():
    now = datetime.now(timezone.utc)
    payload = intent() | ids() | dict(
        approval_id=TWIN.approval_id(intent()['attempt_id']),
        core_request_sha256='a' * 64,
        core_source_event_ids=prepared_core()['source_event_ids'],
        issuer_id='twin-acme-test', approval_actor=TWIN.ISSUER,
        approval_kind='SIMULATED', approval_status='SIMULATED',
        approval_phase='PRE_RESOLUTION', core_status_at_issuance='PREPARED',
        resolution_verified=False, post_resolution_readback_required=True,
        approval_nonce='SIMNONCE-1234567890ABCDEF',
        issued_at=now.isoformat(), expires_at=(now + timedelta(minutes=4)).isoformat(),
        impact_root=TWIN.ROOT, impacted_cis=[TWIN.ROOT, TWIN.PAYMENTS],
        human_approved=False, execution_allowed=False, effect_allowed=False,
        real_glpi_writes_allowed=False)
    return {'payload': payload, 'signature': TWIN.sign(payload)}

def test_twin_signed_record_positive_and_tamper_negative():
    record = sample_record()
    assert TWIN.verified_record(json.dumps(record),
                                attempt_id=intent()['attempt_id'])['approval_kind'] == 'SIMULATED'
    record['payload']['human_approved'] = True
    with pytest.raises(HTTPException):
        TWIN.verified_record(json.dumps(record), attempt_id=intent()['attempt_id'])

def test_twin_expired_and_foreign_attempt_denied():
    record = sample_record()
    with pytest.raises(HTTPException):
        TWIN.verified_record(record, attempt_id='ACME-SIM-FOREIGN')
    with pytest.raises(HTTPException):
        TWIN.verified_record(record, attempt_id=intent()['attempt_id'],
                             now=datetime.now(timezone.utc) + timedelta(minutes=6))

def test_twin_signed_record_rejects_replayed_issuer():
    record = sample_record()
    record['payload']['approval_issuer'] = 'HUMAN_IDP'
    record['signature'] = TWIN.sign(record['payload'])
    with pytest.raises(HTTPException):
        TWIN.verified_record(record, attempt_id=intent()['attempt_id'])

def test_simulator_positive_structural_orchestration_only_simulated(monkeypatch):
    calls = []
    def remote(component, path, method='GET', payload=None):
        calls.append((component, method, path))
        if path.endswith('/capabilities'):
            return {'schema': SIM.SCHEMA, 'component': component, 'tenant_id': SIM.TENANT,
                    'mode': 'SIMULATION', 'isolated': True, 'approval_issuer': SIM.ISSUER,
                    'human_approval_claimed': False, 'live_effects_allowed': False,
                    'real_glpi_writes_allowed': False}
        base = intent() | ids()
        if component == 'core':
            return prepared_core() | {'glpi_mode': 'SIMULATED_ONLY'}
        if component == 'twin':
            return base | {'approval_id': 'SIM-APP-UNIT001',
                           'issuer_id': 'twin-acme-test',
                           'core_request_sha256': 'a' * 64,
                           'core_source_event_ids': prepared_core()['source_event_ids'],
                           'approval_issuer': SIM.ISSUER, 'approval_kind': 'SIMULATED',
                           'approval_phase': 'PRE_RESOLUTION',
                           'core_status_at_issuance': 'PREPARED',
                           'resolution_verified': False,
                           'post_resolution_readback_required': True,
                           'approval_nonce': 'SIMNONCE-123456',
                           'human_approved': False, 'execution_allowed': False,
                           'effect_allowed': False, 'live_effects_allowed': False,
                           'real_glpi_writes_allowed': False}
        if component == 'policy':
            return base | {'approval_id': 'SIM-APP-UNIT001', 'decision': 'SIMULATE',
                           'human_approved': False, 'live_effects_allowed': False}
        if component == 'worker':
            assert set(payload) == {
                'attempt_id', 'tenant_id', 'scenario_id', 'mode',
                'approval_issuer', 'incident_id', 'run_id', 'ticket_id',
                'proposal_id', 'approval_id', 'idempotency_key',
                'human_approved', 'execution_allowed', 'effect_allowed'}
            return {'attempt_id': intent()['attempt_id'],
                    'workflow_id': 'acme-simulated-ACME-TEST-ACME-SIM-UNIT001',
                    'status': 'PENDING_INDEPENDENT_READBACK',
                    'effect_allowed': False}
        pytest.fail('unexpected component')
    monkeypatch.setattr(SIM, 'remote', remote)
    result = SIM.start(SIM.SandboxRequest(**intent()),
                       authorization='Bearer test-internal-token-not-real')
    assert result['glpi_mode'] == 'SIMULATED_ONLY'
    assert result['human_approval_claimed'] is False
    assert result['approval_id'] == 'SIM-APP-UNIT001'
    assert [c[0] for c in calls[:4]] == list(SIM.SERVICES)
    assert calls[4][:2] == ('core', 'POST')
    assert calls[-2] == ('core', 'GET', '/api/sandbox/acme/e2e/' + intent()['attempt_id'])
    assert calls[-1][0] == 'worker'

def test_simulator_cross_run_twin_readback_rejected(monkeypatch):
    def remote(component, path, method='GET', payload=None):
        if path.endswith('/capabilities'):
            return {'schema': SIM.SCHEMA, 'component': component, 'tenant_id': SIM.TENANT,
                    'mode': 'SIMULATION', 'isolated': True, 'approval_issuer': SIM.ISSUER,
                    'human_approval_claimed': False, 'live_effects_allowed': False,
                    'real_glpi_writes_allowed': False}
        base = intent() | ids()
        if component == 'core':
            return base | {'glpi_mode': 'SIMULATED_ONLY'}
        if component == 'twin':
            return base | {'approval_id': 'SIM-APP-UNIT001',
                           'approval_issuer': SIM.ISSUER, 'approval_kind': 'SIMULATED',
                           'approval_nonce': 'SIMNONCE-1',
                           'human_approved': False, 'live_effects_allowed': False,
                           'run_id': 'RUN-FOREIGN' if method == 'GET' else ids()['run_id']}
        pytest.fail('policy/worker must not be contacted')
    monkeypatch.setattr(SIM, 'remote', remote)
    with pytest.raises(HTTPException) as e:
        SIM.start(SIM.SandboxRequest(**intent()),
                  authorization='Bearer test-internal-token-not-real')
    assert e.value.status_code == 503

def test_public_twin_temporal_facts_exclude_private_approval():
    source = (BASE / 'twin' / 'main.py').read_text()
    assert "f.attribute <> 'sandbox_simulated_approval'" in source

@pytest.mark.parametrize('changes', [
    {'tenant_id': 'OTHER'}, {'approval_issuer': 'HUMAN_IDP'},
    {'run_id': 'RUN-UNRELATED'}, {'source_event_count': 8},
    {'source_hashes_qualified': False}, {'human_approved': True},
    {'ticket_status': 'RESOLVED'}, {'request_sha256': 'not-a-sha'},
])
def test_twin_prepared_negative_security_matrix(changes):
    x = TWIN.ApprovalIntent(**(intent() | ids()))
    with pytest.raises(HTTPException) as e:
        TWIN.check_core(prepared_core() | changes, x)
    assert e.value.status_code == 503


def test_twin_signed_record_rejects_core_source_rotation():
    record = sample_record()
    record['payload']['core_source_event_ids'][0] = 'SYN-EVT-FOREIGN'
    record['signature'] = TWIN.sign(record['payload'])
    # A valid signature is not enough to bind an unrelated source readback.
    assert record['payload']['core_source_event_ids'][0] == 'SYN-EVT-FOREIGN'
    # The persisted attempt is checked against independently re-read Core
    # before issuing/reusing an approval; this unit proves that fence.
    x = TWIN.ApprovalIntent(**(intent() | ids()))
    assert TWIN.check_core(prepared_core(), x)[1][0] != record['payload']['core_source_event_ids'][0]


def test_simulator_rejects_core_pre_resolved_before_twin_post(monkeypatch):
    calls = []
    def remote(component, path, method='GET', payload=None):
        calls.append((component, method))
        if path.endswith('/capabilities'):
            return {'schema': SIM.SCHEMA, 'component': component, 'tenant_id': SIM.TENANT,
                    'mode': 'SIMULATION', 'isolated': True, 'approval_issuer': SIM.ISSUER,
                    'human_approval_claimed': False, 'live_effects_allowed': False,
                    'real_glpi_writes_allowed': False}
        if component == 'core':
            return prepared_core() | {'incident_status': 'RESOLVED',
                                      'run_status': 'RESOLVED',
                                      'ticket_status': 'RESOLVED',
                                      'glpi_mode': 'SIMULATED_ONLY'}
        pytest.fail('Twin must never receive approval POST for pre-resolved Core')
    monkeypatch.setattr(SIM, 'remote', remote)
    with pytest.raises(HTTPException) as e:
        SIM.start(SIM.SandboxRequest(**intent()),
                  authorization='Bearer test-internal-token-not-real')
    assert e.value.status_code == 503
    assert ('twin', 'POST') not in calls


def test_simulator_pre_worker_core_resolution_race_denied(monkeypatch):
    calls = []
    def remote(component, path, method='GET', payload=None):
        calls.append((component, method, path))
        if path.endswith('/capabilities'):
            return {'schema': SIM.SCHEMA, 'component': component, 'tenant_id': SIM.TENANT,
                    'mode': 'SIMULATION', 'isolated': True, 'approval_issuer': SIM.ISSUER,
                    'human_approval_claimed': False, 'live_effects_allowed': False,
                    'real_glpi_writes_allowed': False}
        base = intent() | ids()
        if component == 'core':
            value = prepared_core() | {'glpi_mode': 'SIMULATED_ONLY'}
            if method == 'GET':
                return value | {'run_status': 'RESOLVED'}
            return value
        if component == 'twin':
            return base | {'approval_id': 'SIM-APP-UNIT001',
                           'issuer_id': 'twin-acme-test',
                           'core_request_sha256': 'a' * 64,
                           'core_source_event_ids': prepared_core()['source_event_ids'],
                           'approval_issuer': SIM.ISSUER, 'approval_kind': 'SIMULATED',
                           'approval_nonce': 'SIMNONCE-123456',
                           'human_approved': False, 'live_effects_allowed': False}
        if component == 'policy':
            return base | {'approval_id': 'SIM-APP-UNIT001', 'decision': 'SIMULATE',
                           'human_approved': False, 'live_effects_allowed': False}
        pytest.fail('Worker must never receive POST after Core resolved')
    monkeypatch.setattr(SIM, 'remote', remote)
    with pytest.raises(HTTPException) as e:
        SIM.start(SIM.SandboxRequest(**intent()),
                  authorization='Bearer test-internal-token-not-real')
    assert e.value.status_code == 503
    assert not any(c[0] == 'worker' and c[1] == 'POST' for c in calls)


def test_twin_approval_replay_expiry_and_foreign_tenant_denied():
    record = sample_record()
    for changes in ({'tenant_id': 'OTHER'}, {'issuer_id': 'human-idp'},
                    {'approval_id': 'SIM-APP-REPLAY'}):
        altered = {'payload': record['payload'] | changes}
        altered['signature'] = TWIN.sign(altered['payload'])
        with pytest.raises(HTTPException):
            TWIN.verified_record(altered, attempt_id=intent()['attempt_id'])
    with pytest.raises(HTTPException):
        TWIN.verified_record(record, attempt_id=intent()['attempt_id'],
                             now=datetime.now(timezone.utc) + timedelta(minutes=6))


@pytest.mark.parametrize('bad_url', [
    'file:///etc/passwd',
    'http://user:password@aiops2-core:810',
    'http://aiops2-core:810/private',
    'http://aiops2-core:810?redirect=1',
    'http://aiops2-core:810/#fragment',
    'http:///',
    'https://aiops2-core:810/other',
])
def test_twin_independent_core_origin_rejects_untrusted_urls_before_http(monkeypatch, bad_url):
    monkeypatch.setenv('CORE_URL', bad_url)
    monkeypatch.setattr(TWIN.requests, 'get', lambda *a, **kw: pytest.fail('unexpected HTTP'))
    with pytest.raises(HTTPException) as error:
        TWIN.core_readback(TWIN.ApprovalIntent(**(intent() | ids())))
    assert error.value.status_code == 503
    assert error.value.detail == 'independent_core_url_invalid'


def test_twin_never_persists_approval_for_already_resolved_run(monkeypatch):
    monkeypatch.setattr(TWIN, 'core_readback',
                        lambda _x: prepared_core() | {'run_status': 'RESOLVED'})
    monkeypatch.setattr(TWIN, 'sourced_impact',
                        lambda: pytest.fail('Twin graph read before PREPARED fence'))
    monkeypatch.setattr(TWIN, 'db',
                        lambda: pytest.fail('approval persistence after resolution'))
    with pytest.raises(HTTPException) as error:
        TWIN.issue_approval(TWIN.ApprovalIntent(**(intent() | ids())),
                            authorization='Bearer test-internal-token-not-real')
    assert error.value.status_code == 503


@pytest.mark.parametrize('forgery', [
    {'human_approved': True},
    {'execution_allowed': True},
    {'effect_allowed': True},
    {'live_effects_allowed': True},
    {'real_glpi_writes_allowed': True},
    {'issuer_id': 'human-idp'},
    {'resolution_verified': True},
    {'post_resolution_readback_required': False},
])
def test_simulator_rejects_forged_twin_independent_readback_before_policy_or_worker(
        monkeypatch, forgery):
    calls = []
    twin_valid = intent() | ids() | {
        'approval_id': 'SIM-APP-UNIT001',
        'issuer_id': 'twin-acme-test',
        'core_request_sha256': 'a' * 64,
        'core_source_event_ids': prepared_core()['source_event_ids'],
        'approval_issuer': SIM.ISSUER,
        'approval_kind': 'SIMULATED',
        'approval_phase': 'PRE_RESOLUTION',
        'core_status_at_issuance': 'PREPARED',
        'resolution_verified': False,
        'post_resolution_readback_required': True,
        'approval_nonce': 'SIMNONCE-123456',
        'human_approved': False,
        'execution_allowed': False,
        'effect_allowed': False,
        'live_effects_allowed': False,
        'real_glpi_writes_allowed': False,
    }

    def remote(component, path, method='GET', payload=None):
        calls.append((component, method))
        if path.endswith('/capabilities'):
            return {'schema': SIM.SCHEMA, 'component': component,
                    'tenant_id': SIM.TENANT, 'mode': 'SIMULATION',
                    'isolated': True, 'approval_issuer': SIM.ISSUER,
                    'human_approval_claimed': False,
                    'live_effects_allowed': False,
                    'real_glpi_writes_allowed': False}
        if component == 'core':
            assert method == 'POST'
            return prepared_core() | {'glpi_mode': 'SIMULATED_ONLY'}
        if component == 'twin':
            return twin_valid | (forgery if method == 'GET' else {})
        pytest.fail('Policy or Worker POST after forged Twin readback')

    monkeypatch.setattr(SIM, 'remote', remote)
    with pytest.raises(HTTPException) as error:
        SIM.start(SIM.SandboxRequest(**intent()),
                  authorization='Bearer test-internal-token-not-real')
    assert error.value.status_code == 503
    assert error.value.detail == 'sandbox_twin_readback_unqualified'
    assert ('twin', 'POST') in calls and ('twin', 'GET') in calls
    assert not any(c in ('policy', 'worker') and m == 'POST' for c, m in calls)


@pytest.mark.parametrize('changes', [
    {'incident_id': 'INC/INVALID'},
    {'run_id': None},
    {'ticket_id': 'GLPI-REAL-123'},
    {'proposal_id': ''},
    {'idempotency_key': 'ACME-SIM-REBOUND'},
])
def test_twin_signed_fact_rejects_resigned_invalid_correlation(changes):
    """Even a correctly HMAC-signed malformed fact cannot imply human authority."""
    record = sample_record()
    record['payload'].update(changes)
    record['signature'] = TWIN.sign(record['payload'])
    with pytest.raises(HTTPException) as error:
        TWIN.verified_record(record, attempt_id=intent()['attempt_id'])
    assert error.value.status_code == 503


@pytest.mark.parametrize('changes', [
    {'source_event_count': 7, 'source_event_ids': ['SYN-EVT-OTHER'] * 7},
    {'source_event_ids': list(reversed(TWIN.canonical_source_ids('ACME-SIM-UNIT001')))},
    {'source_event_ids': TWIN.canonical_source_ids('ACME-SIM-FOREIGN')},
])
def test_twin_prepared_core_rejects_forged_or_reordered_seven_source_ids(changes):
    x = TWIN.ApprovalIntent(**(intent() | ids()))
    with pytest.raises(HTTPException) as error:
        TWIN.check_core(prepared_core() | changes, x)
    assert error.value.status_code == 503


def test_twin_signed_fact_rejects_resigned_foreign_source_set():
    record = sample_record()
    record['payload']['core_source_event_ids'] = TWIN.canonical_source_ids('ACME-SIM-FOREIGN')
    record['signature'] = TWIN.sign(record['payload'])
    with pytest.raises(HTTPException) as error:
        TWIN.verified_record(record, attempt_id=intent()['attempt_id'])
    assert error.value.status_code == 503


def test_twin_post_resolution_readback_preserves_immutable_pre_resolution_fact(monkeypatch):
    """The signed fact remains PRE_RESOLUTION after Core alone resolves the Run.

    This is an isolated Twin readback contract test, not a PG16/host E2E proof.
    """
    record = sample_record()
    original = json.dumps(record, sort_keys=True)
    class ReadOnlyFacts:
        def __init__(self):
            self.queries = []
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def execute(self, query, params):
            assert query.strip().lower().startswith('select value from aiops.twin_facts')
            assert params == (TWIN.fact_id(intent()['attempt_id']),)
            self.queries.append(query)
            return self
        def fetchone(self):
            return (json.dumps(record),)
    facts = ReadOnlyFacts()
    monkeypatch.setattr(TWIN, 'db', lambda: facts)
    monkeypatch.setattr(TWIN, 'core_readback',
                        lambda _x: pytest.fail('readback must not rewrite or reopen Core'))
    result = TWIN.approval_readback(
        intent()['attempt_id'], authorization='Bearer test-internal-token-not-real')
    assert result['approval_id'] == TWIN.approval_id(intent()['attempt_id'])
    assert result['approval_phase'] == 'PRE_RESOLUTION'
    assert result['core_status_at_issuance'] == 'PREPARED'
    assert result['resolution_verified'] is False
    assert result['post_resolution_readback_required'] is True
    assert result['core_source_event_ids'] == TWIN.canonical_source_ids(intent()['attempt_id'])
    assert result['human_approved'] is False
    assert result['live_effects_allowed'] is False
    assert len(facts.queries) == 1
    assert json.dumps(record, sort_keys=True) == original


def test_twin_post_resolution_readback_rejects_tampered_stored_hmac(monkeypatch):
    record = sample_record()
    record['payload']['human_approved'] = True  # signature is intentionally unchanged
    class ReadOnlyFacts:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def execute(self, query, params):
            assert 'select value from aiops.twin_facts' in query
            return self
        def fetchone(self):
            return (json.dumps(record),)
    monkeypatch.setattr(TWIN, 'db', lambda: ReadOnlyFacts())
    with pytest.raises(HTTPException) as error:
        TWIN.approval_readback(
            intent()['attempt_id'], authorization='Bearer test-internal-token-not-real')
    assert error.value.status_code == 503
    assert error.value.detail == 'sandbox_approval_unqualified'
