import pytest
from fastapi import HTTPException
from portal import acme_historical_san_offline as SAN

def rows():
    return ([(k,v,SAN.NODE_NAMES[k],SAN.SITE,'SIMULATED',SAN.NODE_CRITICALITY[k],1.0) for k,v in SAN.NODES.items()],
            [(k,*v,1,1.0) for k,v in SAN.EDGES.items()])

def test_provenance_rows():
    n,e=rows()
    a=SAN.provenance_snapshot(n,e)
    assert a['graph']['runtime_attested'] is False
    assert a['source_migration'] is None
    assert a['graph_sha256']==SAN.provenance_snapshot(n[::-1],e[::-1])['graph_sha256']

@pytest.mark.parametrize('mutation',['missing','foreign','duplicate','confidence'])
def test_provenance_drift(mutation):
    n,e=rows()
    if mutation=='missing': n.pop()
    if mutation=='foreign': e[0]=(e[0][0],'FOREIGN',*e[0][2:])
    if mutation=='duplicate': e[0]=e[1]
    if mutation=='confidence': n[0]=(*n[0][:-1],0.2)
    with pytest.raises(HTTPException): SAN.provenance_snapshot(n,e)
