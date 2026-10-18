import os
from fastapi import FastAPI,Header,HTTPException
from pydantic import BaseModel
from shared.http import post_json,get_json
from shared.ids import new
app=FastAPI(title='ACME Synthetic Scenario & Replay Engine',version='7.8.0')
CORE=os.getenv('CORE_URL','http://aiops-core:810'); TOKEN=os.getenv('AIOPS_INTERNAL_TOKEN',os.getenv('AIOPS_ADMIN_TOKEN','Newaiops26$'))
class Scenario(BaseModel):name:str;seed:int;scenario_id:str|None=None
class Launch(BaseModel):scenario_id:str='SCN-GOLDEN-PAYMENT-P1';mode:str='DEMO';idempotency_key:str|None=None
@app.get('/health')
def health():return {'status':'ok','component':'simulator','synthetic_only':True,'modes':['DEMO','REPLAY','STORY']}
@app.get('/api/scenarios')
def scenarios():
 # Read-only proxy to the authoritative scenario catalog.
 return get_json(CORE,'/api/dashboard',token=TOKEN)
@app.post('/api/scenarios')
def create(x:Scenario,authorization:str|None=Header(default=None)):
 if (authorization or '').removeprefix('Bearer ')!=TOKEN:raise HTTPException(401,'invalid internal token')
 sid=x.scenario_id or new('SCN'); post_json(CORE,'/api/scenarios/register',{'scenario_id':sid,'name':x.name,'seed':x.seed},token=TOKEN);return {'scenario_id':sid,'name':x.name,'seed':x.seed,'synthetic':True}
@app.post('/api/launch')
def launch(x:Launch,authorization:str|None=Header(default=None)):
 if (authorization or '').removeprefix('Bearer ')!=TOKEN:raise HTTPException(401,'invalid internal token')
 mode=x.mode.upper()
 if mode not in ('DEMO','REPLAY','STORY'):raise HTTPException(422,'simulator cannot launch LIVE')
 key=x.idempotency_key or f'{mode}-{x.scenario_id}-{new("ID")}'
 iid=post_json(CORE,'/api/incidents',{'external_id':key,'title':f'{mode} — {x.scenario_id}','severity':'P1','service_id':'ACME-SVC-PAYMENTS','source':'synthetic-simulator','synthetic':True,'payload':{'scenario_id':x.scenario_id,'mode':mode}},token=TOKEN)['incident_id']
 run=post_json(CORE,'/api/runs',{'mode':mode,'scenario_id':x.scenario_id,'incident_id':iid,'idempotency_key':key},token=TOKEN)
 return post_json(CORE,f"/api/runs/{run['run_id']}/execute",{},token=TOKEN)
@app.post('/api/demo/golden')
def golden(authorization:str|None=Header(default=None)):
 if (authorization or '').removeprefix('Bearer ')!=TOKEN:raise HTTPException(401,'invalid internal token')
 return launch(Launch(),authorization)
