from fastapi import FastAPI
from pydantic import BaseModel
import uuid,time
app=FastAPI(title='AIOps2 Core',version='8.0.0')
class Run(BaseModel): incident_id:str; correlation_id:str; mode:str='DEMO'
@app.get('/health')
def health(): return {'status':'ok','service':'core','version':'8.0.0'}
@app.post('/runs')
def create(r:Run):
    return {'run_id':'RUN-'+uuid.uuid4().hex[:16].upper(),'incident_id':r.incident_id,'correlation_id':r.correlation_id,'mode':r.mode,'state':'CREATED','created_at':time.time()}
