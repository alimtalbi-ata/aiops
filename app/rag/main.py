import os
from fastapi import FastAPI, Header, HTTPException
from shared.http import get_json
app=FastAPI(title='ACME AioOps Evidence Context',version='7.8.0')
EVID=os.getenv('EVIDENCE_URL','http://aiops-evidence:812'); TOKEN=os.getenv('AIOPS_INTERNAL_TOKEN','Newaiops26$')
def auth(a):
    if (a or '').removeprefix('Bearer ')!=TOKEN: raise HTTPException(401,'invalid internal token')
@app.get('/health')
def health(): return {'status':'ok','component':'rag','provenance_first':True}
@app.get('/api/context')
def context(run_id:str|None=None,authorization:str|None=Header(default=None)):
    auth(authorization); return get_json(EVID,'/api/evidence'+(f'?run_id={run_id}' if run_id else ''),token=TOKEN)
