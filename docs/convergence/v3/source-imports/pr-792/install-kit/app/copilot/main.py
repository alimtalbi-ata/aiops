"""ACME-scoped, evidence-first Copilot. Deterministic factual answers until grounded LLM is qualified."""
import os,re
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field
from shared.http import get_json
from copilot.acme_knowledge import retrieve

app=FastAPI(title='ACME AioOps Copilot',version='2.1.0')
CORE=os.getenv('CORE_URL','http://aiops2-core:810')
TWIN=os.getenv('TWIN_URL','http://aiops2-twin:811')
class Q(BaseModel):
    question:str=Field(min_length=3,max_length=2000)
    run_id:str|None=None

def grounded_answer(question, run_id, runs, incidents, nodes, run_detail=None, ledger=None, evidence=None):
    """No cross-tenant retrieval, no fabricated confidence, no execution."""
    q=question.casefold()
    data={'scope':'ACME','question':question,'run_id':run_id,'confidence':None,
          'sources':[],'limitations':['Données de laboratoire ou démo à vérifier via provenance.',
            'Aucune remédiation, approbation HITL ni création de ticket effectuée.'],
          'actions_performed':[]}
    if run_id:
        known=next((r for r in runs if r.get('run_id')==run_id),None)
        if not known:
            data.update(answer='UNKNOWN : run absent du registre ACME accessible.')
            return data
        row=(run_detail or {}).get('run') or known
        events=(run_detail or {}).get('events') or []
        last=events[-1] if events else {}
        claims=['Run '+run_id+': état '+str(row.get('status','UNKNOWN')),
            'Mode '+str(row.get('mode','UNKNOWN')),
            'Incident '+str(row.get('incident_id','UNKNOWN')),
            'Dernier événement '+str(last.get('stage','UNKNOWN'))+'/'+str(last.get('status','UNKNOWN'))]
        data['sources']=['core:/api/runs/'+run_id]
        if any(x in q for x in ['preuve','evidence','métrique','metrique','trace','log']):
            items=(evidence or {}).get('items',[])
            markers=[e for e in items if (e.get('provenance') or {}).get('record_type')=='stage_marker']
            claims.append(str(len(items))+' preuve(s) liées, dont '+str(len(markers))+
                          ' marqueur(s) de déroulement non probant(s) pour un diagnostic.')
            data['sources'].append('core:/api/runs/'+run_id+'/evidence')
        if any(x in q for x in ['critic','analyst','ia','décision','decision','blocage','hitl']):
            analyses=(ledger or {}).get('analyses',[])
            critiques=(ledger or {}).get('critiques',[])
            claims.append(str(len(analyses))+' analyse(s), '+str(len(critiques))+' critique(s) consignées.')
            if critiques:
                c=critiques[-1]
                claims.append('Dernière critique validée='+str(c.get('validated','UNKNOWN'))+
                              '; objections='+str(len(c.get('issues') or [])))
            else:
                claims.append('Aucune critique enregistrée : aucune décision du Critic ne peut être déduite.')
            data['sources'].append('core:/api/runs/'+run_id+'/ai-ledger')
        data['answer']='. '.join(claims)+'.'
        return data
    if any(x in q for x in ['cmdb','infra','topologie','équipement','equipement','ci','service']):
        data['answer']='Inventaire ACME accessible : '+str(len(nodes))+' CI dans le Digital Twin. Aucun diagnostic ne peut être déduit du seul inventaire.'
        data['sources']=['twin:/api/twin/nodes']
        return data
    if any(x in q for x in ['incident','ticket','glpi','itil']):
        data['answer']='ACME : '+str(len(incidents))+' incidents accessibles et '+str(len(runs))+' runs accessibles. La traçabilité GLPI n’est pas confirmée par ces données ; aucun ticket ne sera inventé.'
        data['sources']=['core:/api/incidents','core:/api/runs']
        return data
    data['answer']='UNKNOWN : préciser un run ACME ou poser une question sur les incidents et la CMDB. Les logs, traces et tickets non vérifiés ne sont pas inventés.'
    return data

@app.get('/health')
def health():
    return {'status':'ok','component':'copilot','scope':'ACME',
            'mode':'grounded-read-only','unsupported_claim_policy':'UNKNOWN'}

@app.post('/api/copilot/query')
def query(x:Q):
    if x.run_id and not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',x.run_id):
        raise HTTPException(422,'invalid_run_id')
    runs=get_json(CORE,'/api/runs').get('items',[])
    incidents=get_json(CORE,'/api/incidents').get('items',[])
    nodes=get_json(TWIN,'/api/twin/nodes').get('items',[])
    detail=ledger=evidence=None
    if x.run_id and any(r.get('run_id')==x.run_id for r in runs):
        detail=get_json(CORE,'/api/runs/'+x.run_id)
        ledger=get_json(CORE,'/api/runs/'+x.run_id+'/ai-ledger')
        evidence=get_json(CORE,'/api/runs/'+x.run_id+'/evidence')
    answer=grounded_answer(x.question,x.run_id,runs,incidents,nodes,detail,ledger,evidence)
    docs=retrieve(x.question)
    answer['rag_context']={'scope':'ACME','documents':docs,
       'note':'Références de démonstration synthétiques, non validées comme procédures de production.'}
    return answer
