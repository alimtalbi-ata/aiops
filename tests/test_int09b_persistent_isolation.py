import importlib
import pytest
from fastapi import HTTPException

@pytest.mark.parametrize('service,entry,args',[
 ('core','start',(None,)),('core','resolve',(None,)),('core','readback',('ACME-SIM-UNIT001',)),
 ('twin','issue_approval',(None,)),('twin','approval_readback',('ACME-SIM-UNIT001',)),
 ('policy','start',({},)),('policy','readback',('ACME-SIM-UNIT001',)),
])
def test_unregistered_disabled(service,entry,args):
    m=importlib.import_module(service+'.acme_sandbox_int09')
    assert not hasattr(m,'router')
    with pytest.raises(HTTPException) as e:
        getattr(m,entry)(*args)
    assert e.value.status_code==503
