import os
from fastapi import FastAPI
from pydantic import BaseModel
from shared.http import get_json
app=FastAPI(title='ACME AioOps Copilot',version='2.0.0')
CORE=os.getenv('CORE_URL','http://aiops2-core:810');TWIN=os.getenv('TWIN_URL','http://aiops2-twin:811');EVID=os.getenv('EVIDENCE_URL','http://aiops2-evidence:812')
class Q(BaseModel):question:str;run_id:str|None=None
@app.get('/health')
def health():return {'status':'ok','component':'copilot','mode':'evidence-first','unsupported_claim_policy':'UNKNOWN'}
@app.post('/api/copilot/query')
def query(x:Q):
    d=get_json(CORE,'/api/dashboard');t=get_json(TWIN,'/api/twin/summary'); e=get_json(EVID,'/api/evidence'+(f'?run_id={x.run_id}' if x.run_id else ''))
    claims=[f"Twin: {t['nodes']} nodes and {t['edges']} relationships.",f"Run inventory: {d['runs_total']} runs, {d['open_incidents']} open incidents."]
    if x.run_id:claims.append(f"Evidence linked to run {x.run_id}: {len(e['items'])} records.")
    return {'answer':' '.join(claims)+' Any claim not supported by these authoritative APIs is UNKNOWN.','question':x.question,'sources':['core:/api/dashboard','twin:/api/twin/summary','evidence:/api/evidence'],'confidence':0.90 if e['items'] else 0.78,'limitations':['Synthetic environment unless provenance says otherwise.','No inference from missing evidence.']}
