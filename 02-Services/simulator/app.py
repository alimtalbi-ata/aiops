from fastapi import FastAPI
from uuid import uuid4
app=FastAPI(title='AIOps2 Simulator',version='8.0.0')
@app.get('/health')
def health(): return {'status':'ok','service':'simulator'}
@app.post('/scenarios/{name}')
def scenario(name:str):
    run='RUN-'+uuid4().hex[:16].upper(); inc='INC-'+uuid4().hex[:12].upper(); cor='COR-'+uuid4().hex[:12].upper()
    return {'simulation':True,'scenario':name,'incident_id':inc,'correlation_id':cor,'run':{'run_id':run,'mode':'DEMO','state':'CREATED'}}
