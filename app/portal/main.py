import os,json,html,secrets
from fastapi import FastAPI,HTTPException,Header,Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel,Field
from shared.http import get_json,post_json

app=FastAPI(title='AIOps 2.0 Command Center',version='2.0.1')
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
def bootstrap():return {'dashboard':get_json(CORE,'/api/dashboard'),'runs':get_json(CORE,'/api/runs'),'twin':get_json(TWIN,'/api/twin/summary')}
@app.post('/api/copilot')
def copilot(q:CopilotQuestion, _operator:bool=Depends(require_operator)):
    return safe_upstream(lambda:post_json(COPILOT,'/api/copilot/query',q.model_dump(),timeout=12))

@app.post('/api/demo')
def demo(_operator:bool=Depends(require_operator)):
    def launch():
        iid=post_json(CORE,'/api/incidents',{'external_id':'DEMO-GOLDEN-PAYMENT','title':'Payment latency following FC fabric degradation','severity':'P1','service_id':'ACME-SVC-PAYMENTS','source':'portal-demo','synthetic':True,'payload':{'seed':20261018}},timeout=8)['incident_id']
        run=post_json(CORE,'/api/runs',{'mode':'DEMO','scenario_id':'SCN-GOLDEN-PAYMENT-P1','incident_id':iid,'idempotency_key':'DEMO-GOLDEN-PAYMENT'},timeout=8)
        return post_json(CORE,f"/api/runs/{run['run_id']}/execute",{},timeout=12)
    return safe_upstream(launch)
@app.get('/',response_class=HTMLResponse)
def home():
    d=get_json(CORE,'/api/dashboard');runs=get_json(CORE,'/api/runs')['items'];t=get_json(TWIN,'/api/twin/summary')
    cards=[('Open P1',d['open_p1']),('Incidents',d['open_incidents']),('Running',d['running']),('Blocked',d['blocked']),('Twin nodes',d['twin_nodes']),('Degraded',d['degraded_nodes'])]
    cards_html=''.join(f'<div class="card"><span>{html.escape(str(k))}</span><strong>{v}</strong></div>' for k,v in cards)
    rows=''.join(f'<tr><td><code>{html.escape(str(r["run_id"]))}</code></td><td>{r["mode"]}</td><td><b>{r["status"]}</b></td><td>{r["overall_confidence"]}</td><td>{r["scenario_id"]}</td></tr>' for r in runs[:15]) or '<tr><td colspan="5">UNKNOWN — aucun run</td></tr>'
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>ACME AioOps</title><style>
body{{margin:0;background:#07111d;color:#e9f2f8;font:14px system-ui,Segoe UI,sans-serif}}header{{position:sticky;top:0;background:#0b1c2b;border-bottom:1px solid #25445a;padding:16px 28px;display:flex;justify-content:space-between;z-index:2}}main{{max-width:1500px;margin:auto;padding:26px}}h1{{font-size:34px;margin:0 0 6px}}h2{{margin-top:30px}}.muted{{color:#8fa7b8}}.grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}}.card{{background:#0d2031;border:1px solid #23445b;border-radius:14px;padding:15px;min-height:78px}}.card span{{display:block;color:#9eb5c5;font-size:12px}}.card strong{{display:block;font-size:30px;margin-top:9px}}.two{{display:grid;grid-template-columns:2fr 1fr;gap:16px}}.panel{{background:#0c1d2d;border:1px solid #23445b;border-radius:14px;padding:18px;margin-top:16px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #1d394e;text-align:left}}button{{border:0;border-radius:9px;padding:11px 15px;background:#2188c7;color:#fff;cursor:pointer;margin-right:8px}}button.secondary{{background:#18384e}}textarea{{width:100%;min-height:80px;background:#07131f;color:#fff;border:1px solid #2a4b61;border-radius:9px;padding:10px;box-sizing:border-box}}pre{{white-space:pre-wrap}}code{{color:#b8d8eb}}@media(max-width:1100px){{.grid{{grid-template-columns:repeat(3,1fr)}}.two{{grid-template-columns:1fr}}}}@media(max-width:650px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><header><b>ACME AioOps 2.0</b><span class="muted">Digital Twin · Canonical Run Engine · Evidence · Policy · Copilot</span></header><main><h1>Operations Command Center</h1><div class="muted">Synthetic/demo data is explicitly labelled. Unsupported claims remain UNKNOWN.</div><div class="grid" style="margin-top:20px">{cards_html}</div><div class="panel"><label for="operator-token">Operator token (not saved)</label><input id="operator-token" type="password" autocomplete="current-password" maxlength="256" style="width:100%;max-width:520px;display:block;margin:8px 0 14px;padding:10px;background:#07131f;color:#fff;border:1px solid #2a4b61;border-radius:9px"/><button onclick="demo()">Launch Golden DEMO</button><button class="secondary" onclick="location.reload()">Refresh</button><span id="demo" class="muted"></span></div><div class="two"><section class="panel"><h2>Canonical Runs</h2><table><tr><th>Run</th><th>Mode</th><th>Status</th><th>Confidence</th><th>Scenario</th></tr>{rows}</table></section><section class="panel"><h2>Digital Twin</h2><pre>{html.escape(json.dumps(t,indent=2,default=str))}</pre></section></div><section class="panel"><h2>AI Copilot</h2><textarea id="q" placeholder="Ex: Pourquoi le service Payment est-il à risque ? Quelles preuves avons-nous ?"></textarea><button onclick="ask()" style="margin-top:10px">Ask Copilot</button><pre id="a" class="muted"></pre></section></main><script>
function operatorHeaders(extra={{}}){{let token=document.getElementById('operator-token').value;return Object.assign({{'Authorization':'Bearer '+token}},extra)}}
async function showResponse(target,response){{let body;try{{body=await response.json()}}catch{{body={{detail:'Unexpected response from server'}}}}document.getElementById(target).textContent=JSON.stringify(body,null,2);if(response.status===401)document.getElementById(target).textContent='Operator authentication required. Enter a valid token.'}}
async function demo(){{let target=document.getElementById('demo');target.textContent='Launching synthetic DEMO…';try{{let r=await fetch('/api/demo',{{method:'POST',headers:operatorHeaders()}});await showResponse('demo',r);if(r.ok)setTimeout(()=>location.reload(),1500)}}catch{{target.textContent='Portal request failed. Check connectivity and retry.'}}}}
async function ask(){{let q=document.getElementById('q').value.trim();let target=document.getElementById('a');if(!q){{target.textContent='Enter a question first.';return}}if(q.length>4000){{target.textContent='Question exceeds 4,000 characters.';return}}target.textContent='Consulting Copilot…';try{{let r=await fetch('/api/copilot',{{method:'POST',headers:operatorHeaders({{'Content-Type':'application/json'}}),body:JSON.stringify({{question:q}})}});await showResponse('a',r)}}catch{{target.textContent='Copilot request failed. Check connectivity and retry.'}}}}
</script></body></html>'''
