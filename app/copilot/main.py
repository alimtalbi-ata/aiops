import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from shared.http import get_json
app=FastAPI(title='ACME AioOps Copilot',version='7.8.0')
CORE=os.getenv('CORE_URL','http://aiops-core:810');TWIN=os.getenv('TWIN_URL','http://aiops-twin:811');EVID=os.getenv('EVIDENCE_URL','http://aiops-evidence:812'); RAG=os.getenv('RAG_URL','http://aiops-rag:819'); INTEL=os.getenv('INTELLIGENCE_URL','http://aiops-intelligence:818'); TOKEN=os.getenv('AIOPS_INTERNAL_TOKEN','Newaiops26$')
class Q(BaseModel): question:str; run_id:str|None=None
@app.get('/health')
def health(): return {'status':'ok','component':'copilot','mode':'evidence-first'}
@app.post('/api/copilot/query')
def query(x:Q):
    d=get_json(CORE,'/api/dashboard',token=TOKEN); path='/api/twin/graph'+(f'?run_id={x.run_id}' if x.run_id else '')
    t=get_json(TWIN,path,token=TOKEN); e=get_json(EVID,'/api/evidence'+(f'?run_id={x.run_id}' if x.run_id else ''),token=TOKEN)
    items=e.get('items',[])
    analysis=None
    claims=[]; citations=[]
    if x.run_id:
        if items:
            claims.append(f"Le run {x.run_id} dispose de {len(items)} preuves citées.")
            citations=[{'evidence_id':z['evidence_id'],'source':z['source'],'claim':z['claim'],'hash':z['payload_hash']} for z in items]
        else:
            claims.append(f"Aucune preuve n'est disponible pour le run {x.run_id}.")
    claims.append(f"Le Twin expose {len(t['nodes'])} nœuds et {len(t['edges'])} relations.")
    claims.append(f"Le Command Center compte {d['runs_total']} runs et {d['open_incidents']} incidents ouverts.")
    return {'answer':' '.join(claims)+' Toute affirmation non couverte par ces sources est UNKNOWN.','question':x.question,'confidence_basis':'evidence_count_and_source_presence','confidence':None if not items else min(1.0,0.5+0.05*len(items)),'citations':citations,'sources':['core:/api/dashboard',f'twin:{path}',f'evidence:/api/evidence'+(f'?run_id={x.run_id}' if x.run_id else '')]}
