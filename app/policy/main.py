from fastapi import FastAPI
from pydantic import BaseModel,Field
app=FastAPI(title='ACME Policy Engine',version='2.0.0')
class Decision(BaseModel): mode:str;command:str;severity:str;confidence:float=Field(ge=0,le=1);evidence_count:int=Field(ge=0);critic_validated:bool=True;redundancy_ok:bool=True
@app.get('/health')
def health():return {'status':'ok','component':'policy','fail_closed':True}
@app.post('/api/policy/check')
def check(x:Decision):
    if x.mode=='LIVE' and (x.command in ('RESOLVE','REMEDIATE') or not x.critic_validated):return {'state':'BLOCKED','decision':'HUMAN_APPROVAL','reason':'LIVE action requires verified evidence, critic validation and explicit approval'}
    if x.evidence_count==0:return {'state':'UNKNOWN','decision':'HUMAN_APPROVAL','reason':'no evidence available'}
    if x.mode in ('DEMO','REPLAY','STORY'):return {'state':'PASS','decision':'SIMULATE','reason':'synthetic mode: no production mutation permitted'}
    if x.confidence>=.90 and x.critic_validated and x.redundancy_ok:return {'state':'PASS','decision':'ALLOW','reason':'evidence and safety conditions satisfied'}
    return {'state':'BLOCKED','decision':'HUMAN_APPROVAL','reason':'confidence/safety threshold not met'}
@app.get('/metrics')
def metrics(): return 'aiops_policy_up 1\n'
