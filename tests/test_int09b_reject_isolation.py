import json
import pytest
from core import hitl_reject_delivery_int09 as m

@pytest.mark.parametrize('entry,args',[(m.claim_reject,('tenant',{})),(m.ack_reject,('tenant','event',{})),(m.terminal_reject,('tenant','event',{}))])
def test_disabled(entry,args):
    assert not hasattr(m,'router')
    r=entry(*args)
    assert r.status_code==503
    body=json.loads(r.body)
    assert body['execution_allowed'] is False
    assert body['effect_allowed'] is False
    assert body['status']=='UNKNOWN'
