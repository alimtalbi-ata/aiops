import pytest
from portal.acme_historical_bridge_offline import historical_admission_v1
from test_acme_historical_golden_offline import sample_record,KEY
from copy import deepcopy

def call(rows,second, signed=None):
    return historical_admission_v1({'snapshot_id':'SNAP-001'}, {}, rows,second,{}, {},
        signed_twin=signed,test_key=KEY,as_of_utc='2026-11-18T12:00:00Z')

def test_missing():
    assert call(None,None)['qualification']=='BLOCK'

@pytest.mark.parametrize('field',['impact_incident_id','snapshot_id','parent_snapshot_id','version'])
def test_no_inferred_fields(field):
    row={'content':{'content':{'impact_incident_id':'INC-002','snapshot_id':'SNAP-001','parent_snapshot_id':None,'version':1}}}
    rows={k:deepcopy(row) for k in ('core','twin','policy')}
    del rows['core']['content']['content'][field]
    before=deepcopy(rows)
    r=call(rows,row,sample_record())
    assert r['reason']=='HISTORICAL_FIELD_MISSING:'+field
    assert r['qualification']=='BLOCK'
    assert r['runtime_attested'] is False
    assert r['execution_allowed'] is False
    assert rows==before

@pytest.mark.parametrize('version',[True,-1,'1'])
def test_invalid_version(version):
    row={'content':{'content':{'impact_incident_id':'INC-002','snapshot_id':'SNAP-001','parent_snapshot_id':None,'version':version}}}
    r=call({k:row for k in ('core','twin','policy')},row,sample_record())
    assert r['qualification']=='REJECT'
    assert r['resolution_authorized'] is False
