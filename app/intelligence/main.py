import os
from fastapi import FastAPI, Header, HTTPException
from shared.http import get_json
app=FastAPI(title='ACME AioOps Intelligence',version='7.8.0')
TWIN=os.getenv('TWIN_URL','http://aiops-twin:811'); RAG=os.getenv('RAG_URL','http://aiops-rag:819'); TOKEN=os.getenv('AIOPS_INTERNAL_TOKEN','Newaiops26$')
def auth(a):
    if (a or '').removeprefix('Bearer ')!=TOKEN: raise HTTPException(401,'invalid internal token')
@app.get('/health')
def health(): return {'status':'ok','component':'intelligence','evidence_first':True}
@app.post('/api/analyze')
def analyze(x:dict,authorization:str|None=Header(default=None)):
    auth(authorization); run_id=x.get('run_id'); twin=get_json(TWIN,'/api/twin/graph'+(f'?run_id={run_id}' if run_id else ''),token=TOKEN); evidence=get_json(RAG,'/api/context'+(f'?run_id={run_id}' if run_id else ''),token=TOKEN)
    return {'run_id':run_id,'classification':x.get('classification','UNKNOWN'),'severity':x.get('severity','UNKNOWN'),'root_cause':{'hypothesis':'Evidence-backed analysis pending model adapter','confidence':0.0,'evidence_ids':[e['evidence_id'] for e in evidence.get('items',[])]},'impact':{'nodes':len(twin.get('nodes',[])),'edges':len(twin.get('edges',[]))},'recommendation':('SIMULATE' if x.get('mode') in ('DEMO','REPLAY','STORY') else 'HUMAN_APPROVAL'),'confidence':0.0,'unknowns':['model adapter not configured'],'evidence':evidence.get('items',[])}
