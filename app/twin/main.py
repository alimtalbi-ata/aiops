from fastapi import FastAPI,HTTPException,Header
from shared.db import db
app=FastAPI(title='ACME Digital Twin',version='7.8.0')
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
def graph(run_id:str|None=None):
    with db() as c:
        if run_id:
            ns=c.execute("""select n.node_id,n.type,n.name,n.site,coalesce(o.state,n.state),coalesce(o.health,n.health),n.criticality,n.confidence
                            from aiops.twin_nodes n left join aiops.twin_run_overrides o on o.node_id=n.node_id and o.run_id=%s""",(run_id,)).fetchall()
        else:
            ns=c.execute('select node_id,type,name,site,state,health,criticality,confidence from aiops.twin_nodes').fetchall()
        es=c.execute('select edge_id,source_id,target_id,relation_type,redundancy,confidence from aiops.twin_edges').fetchall()
    nk=['node_id','type','name','site','state','health','criticality','confidence']; ek=['edge_id','source_id','target_id','relation_type','redundancy','confidence']; return {'run_id':run_id,'nodes':[dict(zip(nk,x)) for x in ns],'edges':[dict(zip(ek,x)) for x in es]}

@app.get('/api/twin/impact/{node_id}')
def impact(node_id:str):
    with db() as c:
        if not c.execute('select 1 from aiops.twin_nodes where node_id=%s',(node_id,)).fetchone():raise HTTPException(404,'node not found')
        rows=c.execute("with recursive down(id,depth) as (select %s,0 union select e.target_id,d.depth+1 from aiops.twin_edges e join down d on e.source_id=d.id where d.depth<8) select n.node_id,n.type,n.name,n.criticality,d.depth from down d join aiops.twin_nodes n on n.node_id=d.id order by d.depth,n.criticality desc",(node_id,)).fetchall()
    k=['node_id','type','name','criticality','depth']; return {'root':node_id,'affected':[dict(zip(k,x)) for x in rows]}
@app.get('/api/twin/at')
def at(known_at:str):
    with db() as c:r=c.execute("select f.fact_id,f.node_id,f.attribute,f.value,f.valid_from,f.valid_to,f.known_at,f.confidence from aiops.twin_facts f where f.known_at<=%s and f.valid_from<=%s and (f.valid_to is null or f.valid_to>%s) order by f.node_id,f.attribute",(known_at,known_at,known_at)).fetchall()
    k=['fact_id','node_id','attribute','value','valid_from','valid_to','known_at','confidence']; return {'known_at':known_at,'facts':[dict(zip(k,x)) for x in r]}
import os
from pydantic import BaseModel
from shared.ids import new
SIM_TOKEN=os.getenv('AIOPS_ADMIN_TOKEN','Newaiops26$')
class SyntheticEvent(BaseModel):action:str;target_node_id:str|None=None;payload:dict={};run_id:str|None=None
@app.post('/api/twin/synthetic-event')
def synthetic_event(x:SyntheticEvent,authorization:str|None=Header(default=None)):
    if (authorization or '').removeprefix('Bearer ')!=SIM_TOKEN: raise HTTPException(401,'invalid token')
    if not x.run_id: raise HTTPException(422,'run_id required')
    with db() as c:
        if x.action=='SET_STATE' and x.target_node_id:
            p=x.payload; c.execute("insert into aiops.twin_run_overrides(run_id,node_id,state,health,payload) values(%s,%s,%s,%s,%s) on conflict(run_id,node_id) do update set state=excluded.state,health=excluded.health,observed_at=now(),known_at=now(),payload=excluded.payload",(x.run_id,x.target_node_id,p.get('state','UNKNOWN'),p.get('health'),__import__('json').dumps({'synthetic':True,'run_id':x.run_id})))
        elif x.action=='OBSERVE' and x.target_node_id:
            p=x.payload;c.execute('insert into aiops.observations(observation_id,run_id,node_id,metric,value,unit,observed_at,status,payload) values(%s,%s,%s,%s,%s,%s,now(),%s,%s)',(new('OBS'),x.run_id,x.target_node_id,p.get('metric','synthetic'),p.get('value'),p.get('unit'),p.get('status','UNKNOWN'),__import__('json').dumps({'run_id':x.run_id,'synthetic':True})))
    return {'status':'PASS','action':x.action,'target_node_id':x.target_node_id,'synthetic':True}

@app.get('/metrics')
def metrics():
    with db() as c:
        n,d,f=c.execute("select count(*),count(*) filter(where state='DEGRADED'),count(*) filter(where state='FAILED') from aiops.twin_nodes").fetchone()
    return f'aiops_twin_nodes {n}\naiops_twin_degraded {d}\naiops_twin_failed {f}\n'
