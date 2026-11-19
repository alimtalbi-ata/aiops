from fastapi import FastAPI,HTTPException,Header
from shared.db import db
app=FastAPI(title='ACME Digital Twin',version='2.0.0')
@app.get('/health')
def health(): return {'status':'ok','component':'twin','authority':'canonical-topology'}
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

# Explicit relation semantics: unknown types are excluded, never guessed.
REVERSE_DEPENDENCIES = frozenset(("DEPENDS_ON", "RUNS_ON", "USES", "PATH", "HOSTED_ON"))
FORWARD_SIMULATION = frozenset(("SIMULATED_FC_PATH", "SIMULATED_DEPENDS_ON",
                               "SIMULATED_REPLICATION", "SIMULATED_BACKUP"))

def potential_dependents(snapshot, root):
    from collections import deque
    nodes = {n["node_id"]: n for n in snapshot["nodes"]}
    if root not in nodes:
        raise KeyError(root)
    adjacency = {}
    excluded = set()
    for e in sorted(snapshot["edges"], key=lambda e: e["edge_id"]):
        a, b, kind = e["source_id"], e["target_id"], e["relation_type"]
        if kind in REVERSE_DEPENDENCIES:
            a, b = b, a
        elif kind not in FORWARD_SIMULATION:
            excluded.add(kind)
            continue
        if a in nodes and b in nodes:
            adjacency.setdefault(a, []).append((b, e["edge_id"]))
    visited = {root}
    queue = deque([(root, [], [root])])
    results = []
    truncated = False
    while queue:
        node, edges, path = queue.popleft()
        results.append({**nodes[node], "depth": len(edges),
                        "path_node_ids": path, "path_edge_ids": edges})
        for target, edge in adjacency.get(node, []):
            if target in visited:
                continue
            if len(edges) >= 8:
                truncated = True
                continue
            visited.add(target)
            queue.append((target, edges + [edge], path + [target]))
    return {"root": root, "affected": results, "impact": "POTENTIAL_ONLY",
            "causality": "UNKNOWN", "redundancy_verified": False,
            "excluded_relation_types": sorted(excluded), "depth_limit": 8,
            "truncated": truncated, "path_selection": "one shortest path per node",
            "live_remediation_authorized": False}

@app.get('/api/twin/dependents/{node_id}')
def dependents(node_id: str):
    try:
        return potential_dependents(graph(), node_id)
    except KeyError:
        raise HTTPException(404, 'node not found')

@app.get('/api/twin/at')
def at(known_at:str):
    with db() as c:r=c.execute("select f.fact_id,f.node_id,f.attribute,f.value,f.valid_from,f.valid_to,f.known_at,f.confidence from aiops.twin_facts f where f.known_at<=%s and f.valid_from<=%s and (f.valid_to is null or f.valid_to>%s) order by f.node_id,f.attribute",(known_at,known_at,known_at)).fetchall()
    k=['fact_id','node_id','attribute','value','valid_from','valid_to','known_at','confidence']; return {'known_at':known_at,'facts':[dict(zip(k,x)) for x in r]}
import os
from pydantic import BaseModel
from shared.ids import new
SIM_TOKEN=os.getenv('AIOPS_ADMIN_TOKEN')
if not SIM_TOKEN: raise RuntimeError('AIOPS_ADMIN_TOKEN must be configured')
class SyntheticEvent(BaseModel):action:str;target_node_id:str|None=None;payload:dict={};run_id:str|None=None
@app.post('/api/twin/synthetic-event')
def synthetic_event(x:SyntheticEvent,authorization:str|None=Header(default=None)):
    if (authorization or '').removeprefix('Bearer ')!=SIM_TOKEN: raise HTTPException(401,'invalid token')
    if not x.run_id: raise HTTPException(422,'run_id required')
    with db() as c:
        if x.action=='SET_STATE' and x.target_node_id:
            p=x.payload; c.execute('update aiops.twin_nodes set state=%s,health=%s,known_at=now() where node_id=%s',(p.get('state','UNKNOWN'),p.get('health'),x.target_node_id))
            c.execute('insert into aiops.twin_facts(fact_id,node_id,attribute,value,valid_from,confidence) values(%s,%s,\'state\',%s,now(),1.0)',(new('FACT'),x.target_node_id,__import__('json').dumps({'state':p.get('state'),'run_id':x.run_id,'synthetic':True})))
        elif x.action=='OBSERVE' and x.target_node_id:
            p=x.payload;c.execute('insert into aiops.observations(observation_id,node_id,metric,value,unit,observed_at,status,payload) values(%s,%s,%s,%s,%s,now(),%s,%s)',(new('OBS'),x.target_node_id,p.get('metric','synthetic'),p.get('value'),p.get('unit'),p.get('status','UNKNOWN'),__import__('json').dumps({'run_id':x.run_id,'synthetic':True})))
    return {'status':'PASS','action':x.action,'target_node_id':x.target_node_id,'synthetic':True}

@app.get('/metrics')
def metrics():
    with db() as c:
        n,d,f=c.execute("select count(*),count(*) filter(where state='DEGRADED'),count(*) filter(where state='FAILED') from aiops.twin_nodes").fetchone()
    return f'aiops_twin_nodes {n}\naiops_twin_degraded {d}\naiops_twin_failed {f}\n'
