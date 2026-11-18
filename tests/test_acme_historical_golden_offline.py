"""Golden #802 adapted offline predicates; test key only."""
import pytest, hmac, hashlib, json
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from portal import acme_historical_twin_offline as TWIN, acme_historical_core_offline as CORE, acme_historical_policy_offline as POLICY
NOW = datetime(2026,11,18,12,tzinfo=timezone.utc)
KEY = b'public-test-fixture-not-a-credential'
def sign(payload):
    return hmac.new(KEY,TWIN.canonical(payload),hashlib.sha256).hexdigest()
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

def sample_record():
    now = NOW
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
    return {'payload': payload, 'signature': sign(payload)}


def verify(record, attempt=None, now=NOW):
    return TWIN.verified_record(record, attempt_id=attempt or intent()['attempt_id'], key=KEY, now=now)

def test_signed_nominal():
    assert verify(sample_record())['approval_kind']=='SIMULATED'

@pytest.mark.parametrize('field,value',[('human_approved',True),('approval_nonce','é'),('approval_nonce',''),('tenant_id','OTHER'),('core_source_event_ids',[]),('approval_issuer','HUMAN_IDP')])
def test_resigned_invalid(field,value):
    row=sample_record()
    row['payload'][field]=value
    row['signature']=sign(row['payload'])
    with pytest.raises(HTTPException):
        verify(row)

def test_tamper_expiry_foreign():
    row=sample_record()
    with pytest.raises(HTTPException): verify(row,now=NOW+timedelta(minutes=6))
    with pytest.raises(HTTPException): verify(row,attempt='ACME-SIM-FOREIGN')
    row['payload']['run_id']='RUN-FOREIGN'
    with pytest.raises(HTTPException): verify(row)

def test_core_fence():
    x=SimpleNamespace(**(intent()|ids()))
    assert TWIN.check_core_fence(x,lambda _:prepared_core())[0]=='a'*64
    rows=iter([prepared_core(),prepared_core()|{'run_status':'RESOLVED'}])
    with pytest.raises(HTTPException): TWIN.check_core_fence(x,lambda _:next(rows))

def test_policy_join():
    c=prepared_core()|{'glpi_mode':'SIMULATED_ONLY'}
    t=verify(sample_record())
    assert POLICY.qualify(intent()['attempt_id'],c,t)==('incident_id','run_id','ticket_id','proposal_id')
    with pytest.raises(HTTPException): POLICY.qualify(intent()['attempt_id'],c|{'source_event_count':7.0},t)

def test_core_pure():
    CORE.validate(SimpleNamespace(**intent()))
    with pytest.raises(HTTPException): CORE.validate(SimpleNamespace(**(intent()|{'mode':'LIVE'})))
    CORE.approval_fresh(NOW,NOW+timedelta(minutes=1),now=NOW)
    with pytest.raises(HTTPException): CORE.approval_fresh(NOW+timedelta(seconds=1),NOW+timedelta(minutes=1),now=NOW)
    assert CORE.terminal_ticket_readback_bound({},'SIM-GLPI-001')
    assert not CORE.terminal_ticket_readback_bound({'ticket_id':None},'SIM-GLPI-001')
