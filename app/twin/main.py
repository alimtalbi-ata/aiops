from fastapi import FastAPI,HTTPException,Header
from shared.db import db
app=FastAPI(title='ACME Digital Twin',version='2.0.0')
@app.get('/health')
def health(): return {'status':'ok','component':'twin','authority':'canonical-topology'}
@app.get('/api/twin/acme-quality')
def acme_quality():
    """Read-only topology integrity audit; findings aren't simulated asset states."""
    with db() as c:
        nodes=c.execute("select node_id,type,name,site,state from aiops.twin_nodes where node_id like 'ACME-%' order by node_id").fetchall()
        edges=c.execute("select source_id,target_id,relation_type from aiops.twin_edges where source_id like 'ACME-%' or target_id like 'ACME-%'").fetchall()
    ids={row[0] for row in nodes}
    missing=sorted({end for a,b,_ in edges for end in (a,b) if end not in ids})
    services=[row[0] for row in nodes if row[1]=='SERVICE']
    links={a for a,b,_ in edges}
    isolated=sorted(ci for ci in services if ci not in links)
    return {'scope':'ACME','nodes':len(nodes),'relationships':len(edges),
            'orphan_edge_endpoints':missing,'services_without_outgoing_relation':isolated,
            'quality_status':'PASS' if not missing and not isolated else 'REVIEW',
            'note':'Structural consistency only; does not prove live asset health.'}


@app.get('/api/twin/summary')
def summary():
    with db() as c:
        n=c.execute('select count(*) from aiops.twin_nodes').fetchone()[0]; e=c.execute('select count(*) from aiops.twin_edges').fetchone()[0]
        by=c.execute('select type,count(*) from aiops.twin_nodes group by type order by type').fetchall()
        states=c.execute('select state,count(*) from aiops.twin_nodes group by state').fetchall()
    return {'nodes':n,'edges':e,'nodes_by_type':dict(by),'states':dict(states)}
@app.get('/api/twin/nodes')
def nodes():
    with db() as c:r=c.execute('select node_id,type,name,site,state,criticality,health,confidence from aiops.twin_nodes order by type,name').fetchall()
    k=['node_id','type','name','site','state','criticality','health','confidence']; return {'items':[dict(zip(k,x)) for x in r]}
@app.get('/api/twin/graph')
def graph():
    with db() as c:
        ns=c.execute('select node_id,type,name,site,state,criticality,health,confidence from aiops.twin_nodes').fetchall(); es=c.execute('select edge_id,source_id,target_id,relation_type,redundancy,confidence from aiops.twin_edges').fetchall()
    nk=['node_id','type','name','site','state','criticality','health','confidence']; ek=['edge_id','source_id','target_id','relation_type','redundancy','confidence']; return {'nodes':[dict(zip(nk,x)) for x in ns],'edges':[dict(zip(ek,x)) for x in es]}
@app.get('/api/twin/impact/{node_id}')
def impact(node_id:str):
    with db() as c:
        if not c.execute('select 1 from aiops.twin_nodes where node_id=%s',(node_id,)).fetchone():raise HTTPException(404,'node not found')
        rows=c.execute("with recursive down(id,depth) as (select %s,0 union select e.target_id,d.depth+1 from aiops.twin_edges e join down d on e.source_id=d.id where d.depth<8) select n.node_id,n.type,n.name,n.criticality,d.depth from down d join aiops.twin_nodes n on n.node_id=d.id order by d.depth,n.criticality desc",(node_id,)).fetchall()
    k=['node_id','type','name','criticality','depth']; return {'root':node_id,'affected':[dict(zip(k,x)) for x in rows]}
@app.get('/api/twin/at')
def at(known_at:str):
    with db() as c:r=c.execute("select f.fact_id,f.node_id,f.attribute,f.value,f.valid_from,f.valid_to,f.known_at,f.confidence from aiops.twin_facts f where f.known_at<=%s and f.valid_from<=%s and (f.valid_to is null or f.valid_to>%s) order by f.node_id,f.attribute",(known_at,known_at,known_at)).fetchall()
    # Historical canonical reads must never silently ingest simulated RUN facts.
    # Synthetic facts are stored alongside canonical facts for audit, but they
    # belong to an isolated qualification plane, not the canonical at-time view.
    import json
    def canonical(row):
        value = row[3]
        if isinstance(value, dict):
            payload = value
        elif isinstance(value, str):
            try:
                payload = json.loads(value)
            except (ValueError, TypeError):
                payload = None
        else:
            payload = None
        return not (isinstance(payload, dict) and payload.get('synthetic') is True)
    k=['fact_id','node_id','attribute','value','valid_from','valid_to','known_at','confidence']
    return {'known_at':known_at,'facts':[dict(zip(k,x)) for x in r if canonical(x)]}
import os
from pydantic import BaseModel
from shared.ids import new
SIM_TOKEN=os.getenv('AIOPS_ADMIN_TOKEN')
if not SIM_TOKEN: raise RuntimeError('AIOPS_ADMIN_TOKEN must be configured')
class SyntheticEvent(BaseModel):action:str;target_node_id:str|None=None;payload:dict={};run_id:str|None=None
@app.post('/api/twin/synthetic-event')
def synthetic_event(x:SyntheticEvent,authorization:str|None=Header(default=None)):
    if (authorization or '').removeprefix('Bearer ')!=SIM_TOKEN: raise HTTPException(401,'invalid token')
    if (not isinstance(x.run_id, str) or not x.run_id or x.run_id != x.run_id.strip()
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in x.run_id)):
        raise HTTPException(422, 'valid run_id required')
    # A synthetic receipt must never claim PASS without a supported operation.
    # Validate before opening a DB transaction; unknown actions fail closed.
    if x.action not in ('SET_STATE', 'OBSERVE'):
        raise HTTPException(422, 'unsupported synthetic action')
    if (not isinstance(x.target_node_id, str) or not x.target_node_id
            or x.target_node_id != x.target_node_id.strip()
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in x.target_node_id)):
        raise HTTPException(422, 'valid target_node_id required')
    # Never claim a successful observation/state transition for empty evidence.
    # Validate before DB access, preserving the read-only topology lookup gate.
    if x.action == 'OBSERVE':
        if not isinstance(x.payload.get('metric'), str) or not x.payload['metric'].strip() or x.payload.get('value') is None:
            raise HTTPException(422, 'observation metric and value required')
        # Evidence must be a finite numeric measurement, not a boolean, object or NaN.
        import math
        value = x.payload['value']
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise HTTPException(422, 'observation value must be a finite number')
        try:
            finite = math.isfinite(value)
        except (OverflowError, ValueError, TypeError):
            finite = False
        if not finite:
            raise HTTPException(422, 'observation value must be a finite number')
    if x.action == 'SET_STATE':
        if not isinstance(x.payload.get('state'), str) or not x.payload['state'].strip():
            raise HTTPException(422, 'state required')
    with db() as c:
        # Fail closed before writing an observation or topology fact.
        if not c.execute('select 1 from aiops.twin_nodes where node_id=%s', (x.target_node_id,)).fetchone():
            raise HTTPException(404, 'target node not found')
        if x.action=='SET_STATE' and x.target_node_id:
            record_id = new('FACT')
            # Synthetic scenario state is evidence, never a canonical node mutation.
            # The canonical graph stays unchanged; scenario consumers read twin_facts.
            p=x.payload
            c.execute('insert into aiops.twin_facts(fact_id,node_id,attribute,value,valid_from,confidence) values(%s,%s,\'state\',%s,now(),1.0)',(record_id,x.target_node_id,__import__('json').dumps({'state':p.get('state'),'run_id':x.run_id,'synthetic':True})))
        elif x.action=='OBSERVE' and x.target_node_id:
            # Qualification observations are scenario facts, never canonical telemetry.
            # Persist run provenance in the same fenced store as synthetic state.
            record_id = new('FACT')
            p=x.payload
            c.execute("insert into aiops.twin_facts(fact_id,node_id,attribute,value,valid_from,confidence) values(%s,%s,%s,%s,now(),1.0)",
                      (record_id,x.target_node_id,'observation',__import__('json').dumps({
                          'metric':p['metric'],'value':p['value'],'unit':p.get('unit'),
                          'status':p.get('status','UNKNOWN'),'run_id':x.run_id,'synthetic':True})))
    return {'status':'PASS','action':x.action,'target_node_id':x.target_node_id,'synthetic':True,
            'run_id':x.run_id,'record_id':record_id,
            'record_type':'twin_fact'}

@app.get('/metrics')
def metrics():
    with db() as c:
        n,d,f=c.execute("select count(*),count(*) filter(where state='DEGRADED'),count(*) filter(where state='FAILED') from aiops.twin_nodes").fetchone()
    return f'aiops_twin_nodes {n}\naiops_twin_degraded {d}\naiops_twin_failed {f}\n'
