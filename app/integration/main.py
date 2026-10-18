import os,asyncio
from fastapi import FastAPI,Header,HTTPException
from shared.http import post_json
app=FastAPI(title="ACME AioOps Integration Boundary",version='7.8.0')
CORE=os.getenv("CORE_URL","http://aiops-core:810"); TOKEN=os.getenv("AIOPS_INTERNAL_TOKEN","Newaiops26$")
GLPI=os.getenv("GLPI_URL","http://aiops-glpi:80"); N8N=os.getenv("N8N_URL","http://aiops-n8n:5678"); DELIVERY=os.getenv("INTEGRATION_DELIVERY","MOCK").upper()
def auth(a):
    if (a or "").removeprefix("Bearer ")!=TOKEN: raise HTTPException(401,"invalid internal token")
@app.get("/health")
def health(): return {"status":"ok","component":"integration","delivery":DELIVERY}
@app.post("/api/glpi/ticket")
def glpi_ticket(x:dict,authorization:str|None=Header(default=None)):
    auth(authorization); return {"accepted":True,"target":"GLPI","idempotency_key":x.get("idempotency_key"),"run_id":x.get("run_id")}
@app.post("/api/n8n/event")
def n8n_event(x:dict,authorization:str|None=Header(default=None)):
    auth(authorization); return {"accepted":True,"target":"n8n","idempotency_key":x.get("idempotency_key"),"run_id":x.get("run_id")}
async def dispatcher():
    await asyncio.sleep(3)
    while True:
        try:
            item=claim=post_json(CORE,'/api/outbox/claim',{},token=TOKEN); item=claim.get('item'); lease_owner=claim.get('lease_owner')
            if not item:
                await asyncio.sleep(1); continue
            success=True; error=None
            if DELIVERY!='MOCK':
                # External adapters are deliberately opt-in. MOCK still records the exact receipt path.
                success=False; error='real integration adapter not enabled'
            if success:
                post_json(CORE,'/api/integration/receipt',{'outbox_id':item['outbox_id'],'target':item['aggregate_type'],'idempotency_key':item['idempotency_key'],'status':'DELIVERED','response':{'mode':DELIVERY}},token=TOKEN)
            post_json(CORE,f"/api/outbox/{item['outbox_id']}/ack",{'success':success,'error':error,'lease_owner':lease_owner},token=TOKEN)
        except Exception:
            await asyncio.sleep(2)
@app.on_event('startup')
async def startup(): asyncio.create_task(dispatcher())
