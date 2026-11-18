"""Explicit synthetic Golden/V4 join; never a runtime observation."""
from copy import deepcopy
import pytest
from portal.acme_runtime_context import digest, RECEIPT
from portal.acme_historical_bridge_offline import historical_admission_v1
from test_acme_historical_golden_offline import sample_record, prepared_core, KEY, sign

NOW='2026-11-18T12:00:00Z'
def fixture():
    signed=sample_record()
    t=signed['payload']
    t['issued_at']=NOW
    t['expires_at']='2026-11-18T12:04:00Z'
    signed['signature']=sign(t)
    intent={k:t[k] for k in RECEIPT+('scenario_id','mode','approval_issuer','idempotency_key','human_approved','execution_allowed','effect_allowed')}
    identity={k:intent[k] for k in RECEIPT}|{'impact_incident_id':'INC-IMPACT-001'}
    expected={k:identity[k] for k in ('tenant_id','incident_id','impact_incident_id','run_id','attempt_id')}|{'snapshot_id':'SNAP-001'}
    common=identity|{'snapshot_id':'SNAP-001','parent_snapshot_id':None,'version':1,'idempotency_key':intent['attempt_id']}
    registry={k:k+'-source' for k in ('core','twin','policy','critic','hitl')}
    policies={v:300 for v in registry.values()}
    def v4(k,c):
        return dict(authority=k,scope='RUNTIME_SANDBOX',source_id=registry[k],source_ref='fixture:'+k,observed_at=NOW,snapshot_id='SNAP-001',content=c,content_sha256=digest(c))
    twin=v4('twin',t|common)
    policy=v4('policy',intent|common|dict(state='PASS',decision='SIMULATE',approval_kind='SIMULATED',human_approval_claimed=False,live_effects_allowed=False,real_glpi_writes_allowed=False))
    core=v4('core',prepared_core()|common|dict(glpi_mode='SIMULATED_ONLY',human_approval_claimed=False,authority_manifest={'twin':digest(twin),'policy':digest(policy)}))
    def envelope(k,c):
        return dict(role=k,source_id=registry[k],classification='STORY_OFFLINE',identity=identity,snapshot_id='SNAP-001',observed_at=NOW,content=c,content_sha256=digest(c))
    rows={k:envelope(k,v) for k,v in [('core',core),('twin',twin),('policy',policy),('critic',dict(decision='ALLOW',core_sha256=digest(core),twin_sha256=digest(twin))),('hitl',dict(kind='SIMULATED',human_approved=False,execution_allowed=False,effect_allowed=False,twin_sha256=digest(twin),policy_sha256=digest(policy)))]}
    return expected,intent,rows,deepcopy(rows['core']),registry,policies,signed

def call(f):
    return historical_admission_v1(*f[:6],signed_twin=f[6],test_key=KEY,as_of_utc=NOW)

def assert_closed(r):
    assert r['binding_status']=='UNBOUND'
    assert r['runtime_freshness']=='UNKNOWN'
    for k in ('runtime_attested','execution_allowed','finish_authorized','resolution_authorized','live_remediation_authorized'):
        assert r[k] is False

def test_nominal():
    f=fixture()
    before=deepcopy(f)
    r=call(f)
    assert r['contract_status']=='CONTRACT_ONLY',r
    assert r['qualification']=='BLOCK'
    assert r['projection']['impact_incident_id']=='INC-IMPACT-001'
    assert_closed(r)
    assert f==before

@pytest.mark.parametrize('mutation,reason',[('signature','HISTORICAL_PREDICATE_REFUSED'),('signed_nonce','HISTORICAL_SIGNED_PAYLOAD_MISMATCH'),('expired','HISTORICAL_PREDICATE_REFUSED'),('foreign','HISTORICAL_PREDICATE_REFUSED')])
def test_after_v4(mutation,reason):
    f=fixture()
    signed=f[6]
    if mutation=='signature': signed['signature']='0'*64
    else:
        key,value={'signed_nonce':('approval_nonce','SIMNONCE-CHANGED'),'expired':('expires_at',NOW),'foreign':('attempt_id','ACME-SIM-FOREIGN')}[mutation]
        signed['payload'][key]=value
        signed['signature']=sign(signed['payload'])
    r=call(f)
    assert r['reason']==reason,r
    assert r['qualification']=='REJECT'
    assert_closed(r)

def test_changed_second_core():
    f=fixture()
    f[3]['content']['content']['version']=2
    f[3]['content']['content_sha256']=digest(f[3]['content']['content'])
    f[3]['content_sha256']=digest(f[3]['content'])
    r=call(f)
    assert r['qualification']=='REJECT'
    assert_closed(r)
