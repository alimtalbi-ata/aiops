import hashlib,json,os,hmac
from fastapi import FastAPI,HTTPException,Header
from pydantic import BaseModel,Field
from shared.db import db
from shared.ids import new
from shared.evidence_identity import canonical_evidence, evidence_digest
app=FastAPI(title='ACME Evidence Service',version='2.0.0')
INTERNAL_TOKEN=os.getenv('AIOPS_INTERNAL_TOKEN','')
def authorize(authorization):
    if not INTERNAL_TOKEN: raise HTTPException(503,'internal_auth_not_configured')
    supplied=(authorization or '').removeprefix('Bearer ')
    if not supplied or not hmac.compare_digest(supplied,INTERNAL_TOKEN):
        raise HTTPException(401,'invalid_internal_token')
class In(BaseModel):
    source: str = Field(min_length=1,max_length=128)
    external_id: str|None = Field(default=None,max_length=256)
    observed_at: str|None = None
    claim: str = Field(min_length=1,max_length=8192)
    confidence: float = Field(ge=0,le=1)
    provenance: dict = Field(default_factory=dict)
    payload: dict = Field(default_factory=dict)
@app.get('/health')
def health():return {'status':'ok','component':'evidence','append_only':True}
@app.get('/api/evidence')
def search(source:str|None=None,run_id:str|None=None,limit:int=100,authorization:str|None=Header(default=None)):
    authorize(authorization)
    if limit<1 or limit>500: raise HTTPException(422,'limit_must_be_between_1_and_500')
    with db() as c:
        if run_id:r=c.execute("select evidence_id,source,external_id,observed_at,known_at,claim,confidence,provenance,payload_hash,payload from aiops.evidence where provenance->>'run_id'=%s order by known_at desc limit %s",(run_id,min(limit,500))).fetchall()
        elif source:r=c.execute("select evidence_id,source,external_id,observed_at,known_at,claim,confidence,provenance,payload_hash,payload from aiops.evidence where source=%s order by known_at desc limit %s",(source,min(limit,500))).fetchall()
        else:r=c.execute("select evidence_id,source,external_id,observed_at,known_at,claim,confidence,provenance,payload_hash,payload from aiops.evidence order by known_at desc limit %s",(min(limit,500),)).fetchall()
    k=['evidence_id','source','external_id','observed_at','known_at','claim','confidence','provenance','payload_hash','payload'];return {'items':[dict(zip(k,x)) for x in r]}
@app.post('/api/evidence')
def create(x:In,authorization:str|None=Header(default=None)):
    authorize(authorization)
    try:
        envelope=canonical_evidence(**x.model_dump())
        digest=evidence_digest(envelope)
    except (ValueError,TypeError) as exc:
        raise HTTPException(422,detail={'code':'invalid_evidence_identity','reason':str(exc)}) from exc
    with db() as c:
        eid=new('EVD')
        inserted=c.execute(
            'insert into aiops.evidence(evidence_id,source,external_id,observed_at,claim,confidence,provenance,payload_hash,payload) '
            'values(%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing returning evidence_id',
            (eid,envelope['source'],envelope['external_id'],envelope['observed_at'],
             envelope['claim'],envelope['confidence'],json.dumps(envelope['provenance']),
             digest,json.dumps(envelope['payload']))
        ).fetchone()
        if inserted:
            return {'evidence_id':inserted[0],'payload_hash':digest,'deduplicated':False,
                    'synthetic':bool(envelope['provenance'].get('synthetic',True))}
        # A conflict can be caused by either the source/external identity or the
        # source/full-envelope digest. Distinguish exact replay from a reused
        # external ID with changed data. Never overwrite append-only evidence.
        if envelope['external_id'] is not None:
            previous=c.execute(
                'select evidence_id,payload_hash from aiops.evidence '
                'where source=%s and external_id=%s',
                (envelope['source'],envelope['external_id'])
            ).fetchone()
        else:
            previous=c.execute(
                'select evidence_id,payload_hash from aiops.evidence '
                'where source=%s and payload_hash=%s',
                (envelope['source'],digest)
            ).fetchone()
        if previous and previous[1]==digest:
            return {'evidence_id':previous[0],'payload_hash':digest,'deduplicated':True,
                    'synthetic':bool(envelope['provenance'].get('synthetic',True))}
        raise HTTPException(409,detail={'code':'evidence_identity_conflict',
                                         'source':envelope['source'],
                                         'external_id':envelope['external_id']})
@app.get('/api/evidence/{eid}')
def get(eid:str,authorization:str|None=Header(default=None)):
    authorize(authorization)
    with db() as c:r=c.execute('select evidence_id,source,external_id,observed_at,known_at,claim,confidence,provenance,payload_hash,payload from aiops.evidence where evidence_id=%s',(eid,)).fetchone()
    if not r:raise HTTPException(404,'evidence not found')
    k=['evidence_id','source','external_id','observed_at','known_at','claim','confidence','provenance','payload_hash','payload'];return dict(zip(k,r))
