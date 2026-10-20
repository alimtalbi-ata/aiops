import hashlib,json,os,hmac
from fastapi import FastAPI,HTTPException,Header
from pydantic import BaseModel,Field
from shared.db import db
from shared.ids import new
app=FastAPI(title='ACME Evidence Service',version='2.0.0')
INTERNAL_TOKEN=os.getenv('AIOPS_INTERNAL_TOKEN','')
def authorize(authorization):
    if not INTERNAL_TOKEN: raise HTTPException(503,'internal_auth_not_configured')
    supplied=(authorization or '').removeprefix('Bearer ')
    if not supplied or not hmac.compare_digest(supplied,INTERNAL_TOKEN):
        raise HTTPException(401,'invalid_internal_token')
class In(BaseModel):source:str;external_id:str|None=None;observed_at:str|None=None;claim:str;confidence:float=Field(ge=0,le=1);provenance:dict={};payload:dict={}
@app.get('/health')
def health():return {'status':'ok','component':'evidence','append_only':True}
@app.get('/api/evidence')
def search(source:str|None=None,run_id:str|None=None,limit:int=100,authorization:str|None=Header(default=None)):
    authorize(authorization)
    with db() as c:
        if run_id:r=c.execute("select evidence_id,source,external_id,observed_at,known_at,claim,confidence,provenance,payload_hash,payload from aiops.evidence where provenance->>'run_id'=%s order by known_at desc limit %s",(run_id,min(limit,500))).fetchall()
        elif source:r=c.execute("select evidence_id,source,external_id,observed_at,known_at,claim,confidence,provenance,payload_hash,payload from aiops.evidence where source=%s order by known_at desc limit %s",(source,min(limit,500))).fetchall()
        else:r=c.execute("select evidence_id,source,external_id,observed_at,known_at,claim,confidence,provenance,payload_hash,payload from aiops.evidence order by known_at desc limit %s",(min(limit,500),)).fetchall()
    k=['evidence_id','source','external_id','observed_at','known_at','claim','confidence','provenance','payload_hash','payload'];return {'items':[dict(zip(k,x)) for x in r]}
@app.post('/api/evidence')
def create(x:In,authorization:str|None=Header(default=None)):
    authorize(authorization)
    payload=json.dumps(x.payload,sort_keys=True,separators=(',',':')); h=hashlib.sha256(payload.encode()).hexdigest()
    with db() as c:
        dup=c.execute('select evidence_id from aiops.evidence where payload_hash=%s and source=%s',(h,x.source)).fetchone()
        if dup:return {'evidence_id':dup[0],'payload_hash':h,'deduplicated':True}
        eid=new('EVD');c.execute('insert into aiops.evidence(evidence_id,source,external_id,observed_at,claim,confidence,provenance,payload_hash,payload) values(%s,%s,%s,%s,%s,%s,%s,%s,%s)',(eid,x.source,x.external_id,x.observed_at,x.claim,x.confidence,json.dumps(x.provenance),h,json.dumps(x.payload)))
    return {'evidence_id':eid,'payload_hash':h,'synthetic':bool(x.provenance.get('synthetic',False))}
@app.get('/api/evidence/{eid}')
def get(eid:str,authorization:str|None=Header(default=None)):
    authorize(authorization)
    with db() as c:r=c.execute('select evidence_id,source,external_id,observed_at,known_at,claim,confidence,provenance,payload_hash,payload from aiops.evidence where evidence_id=%s',(eid,)).fetchone()
    if not r:raise HTTPException(404,'evidence not found')
    k=['evidence_id','source','external_id','observed_at','known_at','claim','confidence','provenance','payload_hash','payload'];return dict(zip(k,r))
