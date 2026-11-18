"""Same synthetic Run across admission, actual Worker function and preterminal."""
import asyncio
from copy import deepcopy
import pytest
from portal.acme_runtime_context import digest, RECEIPT, _utc
from portal.acme_int08_phases import preterminal_v1
from worker.acme_simulated_hitl import simulate_no_effect
from test_int09b_admission_nominal import fixture, call, assert_closed

def chain():
    f=fixture()
    expected,intent,admission,second,registry,policies=f[:6]
    assert call(f)['contract_status']=='CONTRACT_ONLY'
    calls=[]
    async def get(role,path):
        assert path.endswith('/'+intent['attempt_id'])
        calls.append(role)
        return deepcopy(admission[role]['content']['content'])
    receipt=asyncio.run(simulate_no_effect(intent,get=get,now=_utc('2026-11-18T12:00:01Z')))
    assert calls==['core','twin','policy']*2
    history=dict(phase='PREFIX',receipt_sha256=receipt['receipt_sha256'],admission_sha256=digest(admission))
    identity={k:intent[k] for k in RECEIPT}
    post=dict(history_prefix_sha256=digest(history),identity=identity,critic_decision='ALLOW',twin_state='QUALIFIED',policy_decision='SIMULATE',hitl_valid=True,external_effect_count=0,postcheck_verified=True)
    sources={k:k+'-source' for k in ('receipt','history_prefix','postcheck')}
    policies.update({v:300 for v in sources.values()})
    rows={}
    for n,(k,v) in enumerate(zip(sources,(receipt,history,post)),1):
        rows[k]=dict(role=k,source_id=sources[k],classification='STORY_OFFLINE',identity=identity|{'impact_incident_id':expected['impact_incident_id']},snapshot_id=expected['snapshot_id'],observed_at=f'2026-11-18T12:00:0{n}Z',content=v,content_sha256=digest(v))
    return expected,intent,admission,second,registry,rows,sources,policies

def invoke(f):
    r=preterminal_v1(*f,as_of_utc='2026-11-18T12:00:04Z')
    assert_closed(r)
    return r

def test_nominal():
    f=chain()
    before=deepcopy(f)
    r=invoke(f)
    assert r['contract_status']=='CONTRACT_ONLY',r
    assert r['qualification']=='BLOCK'
    assert f==before

@pytest.mark.parametrize('role,field,value',[('receipt','ticket_id','SIM-GLPI-FOREIGN'),('history_prefix','admission_sha256','0'*64),('postcheck','history_prefix_sha256','0'*64),('postcheck','external_effect_count',1)])
def test_adverse(role,field,value):
    f=chain()
    row=f[5][role]
    row['content'][field]=value
    row['content_sha256']=digest(row['content'])
    r=invoke(f)
    assert r['qualification']=='REJECT',r

def test_time_order():
    f=chain()
    f[5]['postcheck']['observed_at']=f[5]['history_prefix']['observed_at']
    assert invoke(f)['qualification']=='REJECT'
