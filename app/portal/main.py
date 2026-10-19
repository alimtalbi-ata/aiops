import os,json,html,secrets
from fastapi import FastAPI,HTTPException,Header,Depends,Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel,Field
from shared.http import get_json,post_json

app=FastAPI(title='AIOps 2.0 Command Center',version='2.0.2')

@app.middleware("http")
async def security_headers(request, call_next):
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    return response
CORE=os.getenv('CORE_URL','http://aiops2-core:810')
COPILOT=os.getenv('COPILOT_URL','http://aiops2-copilot:814')
TWIN=os.getenv('TWIN_URL','http://aiops2-twin:811')
OPERATOR_TOKEN=os.getenv('AIOPS_PORTAL_OPERATOR_TOKEN','').strip()
if not OPERATOR_TOKEN:
    raise RuntimeError('AIOPS_PORTAL_OPERATOR_TOKEN must be configured; portal mutations fail closed')

class CopilotQuestion(BaseModel):
    question:str=Field(min_length=1,max_length=4000)

def require_operator(authorization:str|None=Header(default=None)):
    scheme,sep,credential=(authorization or '').partition(' ')
    if scheme.lower()!='bearer' or not sep or not credential or not secrets.compare_digest(credential,OPERATOR_TOKEN):
        raise HTTPException(status_code=401,detail='operator authentication required',headers={'WWW-Authenticate':'Bearer'})
    return True

def require_same_origin(request:Request):
    origin=request.headers.get("origin")
    if origin:
        expected=f"{request.url.scheme}://{request.headers.get('host','')}"
        if not secrets.compare_digest(origin.rstrip('/'),expected.rstrip('/')):
            raise HTTPException(status_code=403,detail='cross-origin request rejected')
    return True

def safe_upstream(call):
    try:
        return call()
    except HTTPException:
        raise
    except Exception:
        # Never forward internal URLs, upstream bodies, exception text or credentials.
        raise HTTPException(status_code=503,detail='upstream service unavailable; retry later') from None
@app.get('/health')
def health():return {'status':'ok','component':'portal','external_port':7777,'internal_port':777}
@app.get('/api/portal/bootstrap')
def bootstrap(_operator:bool=Depends(require_operator)):
    def load():
        return {'dashboard':get_json(CORE,'/api/dashboard',timeout=8),'runs':get_json(CORE,'/api/runs',timeout=8),'twin':get_json(TWIN,'/api/twin/summary',timeout=8)}
    return safe_upstream(load)

@app.post('/api/copilot')
def copilot(q:CopilotQuestion, _operator:bool=Depends(require_operator), _origin:bool=Depends(require_same_origin)):
    return safe_upstream(lambda:post_json(COPILOT,'/api/copilot/query',q.model_dump(),timeout=12))

@app.post('/api/demo')
def demo(_operator:bool=Depends(require_operator), _origin:bool=Depends(require_same_origin)):
    def launch():
        iid=post_json(CORE,'/api/incidents',{'external_id':'DEMO-GOLDEN-PAYMENT','title':'Payment latency following FC fabric degradation','severity':'P1','service_id':'ACME-SVC-PAYMENTS','source':'portal-demo','synthetic':True,'payload':{'seed':20261018}},timeout=8)['incident_id']
        run=post_json(CORE,'/api/runs',{'mode':'DEMO','scenario_id':'SCN-GOLDEN-PAYMENT-P1','incident_id':iid,'idempotency_key':'DEMO-GOLDEN-PAYMENT'},timeout=8)
        return post_json(CORE,f"/api/runs/{run['run_id']}/execute",{},timeout=12)
    return safe_upstream(launch)
@app.get('/',response_class=HTMLResponse)
def home():
    # Serve only the login shell. Operational data is fetched after operator auth.
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark"><title>AIOps 2.0 Command Center</title><style>
:root{color-scheme:dark;font:15px system-ui,Segoe UI,sans-serif;background:#07111d;color:#e9f2f8}*{box-sizing:border-box}body{margin:0}header{background:#0b1c2b;border-bottom:1px solid #25445a;padding:16px 24px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}main{max-width:1450px;margin:auto;padding:24px}h1{font-size:clamp(26px,4vw,36px);margin:0 0 8px}.muted{color:#9eb5c5}.panel,.card{background:#0c1d2d;border:1px solid #23445b;border-radius:14px;padding:18px}.panel{margin-top:16px}.grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin-top:18px}.card span{display:block;color:#9eb5c5;font-size:12px}.card strong{display:block;font-size:28px;margin-top:8px;overflow-wrap:anywhere}.two{display:grid;grid-template-columns:2fr 1fr;gap:16px}button{border:0;border-radius:9px;padding:11px 15px;background:#2188c7;color:#fff;cursor:pointer}button:disabled{opacity:.5;cursor:wait}input,textarea{width:100%;background:#07131f;color:#fff;border:1px solid #2a4b61;border-radius:9px;padding:11px;margin:8px 0 12px}textarea{min-height:80px}table{width:100%;border-collapse:collapse;display:block;overflow-x:auto}th,td{padding:10px;border-bottom:1px solid #1d394e;text-align:left;white-space:nowrap}pre{white-space:pre-wrap;overflow-wrap:anywhere}.hidden{display:none}.error{color:#ffb3a7}@media(max-width:1100px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}.two{grid-template-columns:1fr}}@media(max-width:600px){main{padding:14px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}header{padding:14px}}
</style></head><body><header><b>AIOps 2.0 · Operations Command Center</b><span class="muted">Evidence · Policy · Digital Twin · Copilot</span></header><main><h1>Operations Command Center</h1><p class="muted">Synthetic/demo data is explicitly labelled. Unsupported claims remain UNKNOWN.</p>
<section class="panel" id="login"><h2>Operator access</h2><label for="operator-token">Operator token</label><input id="operator-token" type="password" autocomplete="current-password" maxlength="256" placeholder="Paste your operator token"><button id="connect" onclick="connect()">Authenticate and load dashboard</button><p id="login-status" class="muted" role="status">The token stays in this page memory only; it is not stored in browser storage.</p></section>
<section id="dashboard" class="hidden"><div class="grid" id="cards"></div><section class="panel"><button onclick="refresh()">Refresh dashboard</button> <button onclick="demo()">Launch synthetic DEMO</button><span id="demo-status" class="muted" role="status"></span></section><div class="two"><section class="panel"><h2>Canonical runs</h2><table><thead><tr><th>Run</th><th>Mode</th><th>Status</th><th>Confidence</th><th>Scenario</th></tr></thead><tbody id="runs"></tbody></table></section><section class="panel"><h2>Digital Twin</h2><pre id="twin"></pre></section></div><section class="panel"><h2>AI Copilot</h2><label for="q">Question</label><textarea id="q" maxlength="4000" placeholder="Why is a service at risk? Which evidence supports the diagnosis?"></textarea><button onclick="ask()">Ask Copilot</button><pre id="answer" class="muted" aria-live="polite"></pre></section></section>
<script>
let operatorToken="";
async function request(path,options={}){const headers=Object.assign({},options.headers||{},{Authorization:"Bearer "+operatorToken});const response=await fetch(path,Object.assign({},options,{headers}));let data;try{data=await response.json()}catch{data={detail:"Unexpected server response"}}if(!response.ok){if(response.status===401){operatorToken="";document.getElementById("dashboard").classList.add("hidden");document.getElementById("login").classList.remove("hidden")}throw new Error(response.status===401?"Authentication failed or expired. Re-enter the operator token.":(data.detail||"Request failed ("+response.status+")"))}return data}
function el(tag,text){const node=document.createElement(tag);node.textContent=text==null?"UNKNOWN":String(text);return node}
function render(data){const d=data.dashboard||{};const metrics=[["Open P1",d.open_p1],["Incidents",d.open_incidents],["Running",d.running],["Blocked",d.blocked],["Twin nodes",d.twin_nodes],["Degraded",d.degraded_nodes]];const cards=document.getElementById("cards");cards.replaceChildren();for(const [name,value] of metrics){const card=el("div","");card.className="card";card.append(el("span",name),el("strong",value)) ;cards.append(card)}const body=document.getElementById("runs");body.replaceChildren();const items=(data.runs&&data.runs.items)||[];if(!items.length){const row=el("tr","");const cell=el("td","UNKNOWN — no runs");cell.colSpan=5;row.append(cell);body.append(row)}for(const r of items.slice(0,15)){const row=el("tr","");for(const value of [r.run_id,r.mode,r.status,r.overall_confidence,r.scenario_id])row.append(el("td",value));body.append(row)}document.getElementById("twin").textContent=JSON.stringify(data.twin,null,2)}
async function refresh(){const status=document.getElementById("login-status");try{const data=await request("/api/portal/bootstrap");render(data);document.getElementById("dashboard").classList.remove("hidden");document.getElementById("login").classList.add("hidden");status.textContent="Authenticated. Operational data loaded."}catch(e){status.textContent=e.message;status.className="error"}}
async function connect(){operatorToken=document.getElementById("operator-token").value.trim();if(!operatorToken){document.getElementById("login-status").textContent="Enter the operator token.";return}document.getElementById("connect").disabled=true;await refresh();document.getElementById("connect").disabled=false}
async function demo(){const status=document.getElementById("demo-status");status.textContent="Launching synthetic DEMO…";try{const data=await request("/api/demo",{method:"POST"});status.textContent=JSON.stringify(data);await refresh()}catch(e){status.textContent=e.message}}
async function ask(){const q=document.getElementById("q").value.trim();const answer=document.getElementById("answer");if(!q){answer.textContent="Enter a question first.";return}answer.textContent="Consulting Copilot…";try{answer.textContent=JSON.stringify(await request("/api/copilot",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:q})}),null,2)}catch(e){answer.textContent=e.message}}
document.getElementById("operator-token").addEventListener("keydown",event=>{if(event.key==="Enter")connect()});
</script></main></body></html>"""
