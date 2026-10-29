import os
from fastapi import FastAPI,Header,HTTPException
from pydantic import BaseModel
from shared.http import post_json,get_json
from shared.ids import new
app=FastAPI(title='ACME Synthetic Scenario & Replay Engine',version='2.0.0')
WORKER=os.getenv('WORKER_URL','http://aiops2-worker:815'); TOKEN=os.getenv('AIOPS_INTERNAL_TOKEN') or os.getenv('AIOPS_ADMIN_TOKEN')
if not TOKEN: raise RuntimeError('AIOPS_INTERNAL_TOKEN or AIOPS_ADMIN_TOKEN must be configured')
class Scenario(BaseModel):name:str;seed:int;scenario_id:str|None=None
class Launch(BaseModel):scenario_id:str='SCN-GOLDEN-PAYMENT-P1';mode:str='DEMO';idempotency_key:str|None=None
@app.get('/health')
def health():return {'status':'ok','component':'simulator','synthetic_only':True,'modes':['DEMO','REPLAY','STORY']}
@app.get('/api/scenarios')
def scenarios():
 # Read-only proxy to the authoritative scenario catalog.
 return get_json(WORKER,'/api/synthetic/scenarios',token=TOKEN)
@app.post('/api/scenarios')
def create(x:Scenario,authorization:str|None=Header(default=None)):
 if (authorization or '').removeprefix('Bearer ')!=TOKEN:raise HTTPException(401,'invalid internal token')

 raise HTTPException(403, 'scenario_registration_requires_control_plane')

@app.post('/api/launch')
def launch(x:Launch,authorization:str|None=Header(default=None)):
 if (authorization or '').removeprefix('Bearer ')!=TOKEN:raise HTTPException(401,'invalid internal token')
 mode=x.mode.upper()
 if mode not in ('DEMO','REPLAY','STORY'):raise HTTPException(422,'simulator cannot launch LIVE')
 key=x.idempotency_key or f'{mode}-{x.scenario_id}-{new("ID")}'
 return post_json(WORKER,'/api/synthetic/launch',{
     'scenario_id':x.scenario_id,
     'mode':mode,
     'idempotency_key':key
 },token=TOKEN)

@app.post('/api/demo/golden')
def golden(authorization:str|None=Header(default=None)):
 if (authorization or '').removeprefix('Bearer ')!=TOKEN:raise HTTPException(401,'invalid internal token')
 return launch(Launch(),authorization)
