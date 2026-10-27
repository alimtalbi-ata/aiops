import os,json,html
from fastapi import FastAPI,Request
from fastapi.responses import HTMLResponse,JSONResponse
from shared.http import get_json,post_json
from portal.portal_integrations import build_navigation, render_navigation_html
app=FastAPI(title='ACME AioOps Command Center',version='2.0.0')
CORE=os.getenv('CORE_URL','http://aiops2-core:810');COPILOT=os.getenv('COPILOT_URL','http://aiops2-copilot:814');TWIN=os.getenv('TWIN_URL','http://aiops2-twin:811')
@app.get('/health')
def health():return {'status':'ok','component':'portal','external_port':os.getenv('AIOPS_PORTAL_HOST_PORT','17777'),'internal_port':777}
@app.get('/api/portal/bootstrap')
def bootstrap():return {'dashboard':get_json(CORE,'/api/dashboard'),'runs':get_json(CORE,'/api/runs'),'twin':get_json(TWIN,'/api/twin/summary')}
@app.get('/api/portal/components')
def components():
    return JSONResponse(build_navigation(),headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
@app.post('/api/copilot')
def copilot(q:dict):return post_json(COPILOT,'/api/copilot/query',q)
@app.post('/api/demo')
def demo():
    iid=post_json(CORE,'/api/incidents',{'external_id':'DEMO-GOLDEN-PAYMENT','title':'Payment latency following FC fabric degradation','severity':'P1','service_id':'ACME-SVC-PAYMENTS','source':'portal-demo','synthetic':True,'payload':{'seed':20261018}})['incident_id']
    run=post_json(CORE,'/api/runs',{'mode':'DEMO','scenario_id':'SCN-GOLDEN-PAYMENT-P1','incident_id':iid,'idempotency_key':'DEMO-GOLDEN-PAYMENT'})
    return post_json(CORE,f"/api/runs/{run['run_id']}/execute")
@app.get('/',response_class=HTMLResponse)
def home():
    d=get_json(CORE,'/api/dashboard');runs=get_json(CORE,'/api/runs')['items'];t=get_json(TWIN,'/api/twin/summary')
    integration_html=render_navigation_html(build_navigation())
    cards=[('Open P1',d['open_p1']),('Incidents',d['open_incidents']),('Running',d['running']),('Blocked',d['blocked']),('Twin nodes',d['twin_nodes']),('Degraded',d['degraded_nodes'])]
    cards_html=''.join(f'<div class="card"><span>{html.escape(str(k))}</span><strong>{v}</strong></div>' for k,v in cards)
    rows=''.join(f'<tr><td><code>{html.escape(str(r["run_id"]))}</code></td><td>{r["mode"]}</td><td><b>{r["status"]}</b></td><td>{r["overall_confidence"]}</td><td>{r["scenario_id"]}</td></tr>' for r in runs[:15]) or '<tr><td colspan="5">UNKNOWN — aucun run</td></tr>'
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>ACME AioOps</title><style>
body{{margin:0;background:#07111d;color:#e9f2f8;font:14px system-ui,Segoe UI,sans-serif}}header{{position:sticky;top:0;background:#0b1c2b;border-bottom:1px solid #25445a;padding:16px 28px;display:flex;justify-content:space-between;z-index:2}}main{{max-width:1500px;margin:auto;padding:26px}}h1{{font-size:34px;margin:0 0 6px}}h2{{margin-top:30px}}.muted{{color:#8fa7b8}}.grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}}.card{{background:#0d2031;border:1px solid #23445b;border-radius:14px;padding:15px;min-height:78px}}.card span{{display:block;color:#9eb5c5;font-size:12px}}.card strong{{display:block;font-size:30px;margin-top:9px}}.two{{display:grid;grid-template-columns:2fr 1fr;gap:16px}}.panel{{background:#0c1d2d;border:1px solid #23445b;border-radius:14px;padding:18px;margin-top:16px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #1d394e;text-align:left}}button{{border:0;border-radius:9px;padding:11px 15px;background:#2188c7;color:#fff;cursor:pointer;margin-right:8px}}button.secondary{{background:#18384e}}textarea{{width:100%;min-height:80px;background:#07131f;color:#fff;border:1px solid #2a4b61;border-radius:9px;padding:10px;box-sizing:border-box}}pre{{white-space:pre-wrap}}code{{color:#b8d8eb}}a{{color:#8fd0ff}}nav a{{margin-left:8px}}@media(max-width:1100px){{.grid{{grid-template-columns:repeat(3,1fr)}}.two{{grid-template-columns:1fr}}}}@media(max-width:650px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><header><b>ACME AioOps 2.0</b><nav><a href="#runs">Runs</a> · <a href="#twin">Twin</a> · <a href="#copilot">Copilot</a> · <a href="#integrations">Intégrations</a></nav></header><main><h1>Operations Command Center</h1><div class="muted">Synthetic/demo data is explicitly labelled. Unsupported claims remain UNKNOWN.</div><div class="grid" style="margin-top:20px">{cards_html}</div><div class="panel"><button onclick="demo()">Launch Golden DEMO</button><button class="secondary" onclick="location.reload()">Refresh</button><span id="demo" class="muted"></span></div><div class="two"><section class="panel" id="runs"><h2>Canonical Runs</h2><table><tr><th>Run</th><th>Mode</th><th>Status</th><th>Confidence</th><th>Scenario</th></tr>{rows}</table></section><section class="panel" id="twin"><h2>Digital Twin</h2><pre>{html.escape(json.dumps(t,indent=2,default=str))}</pre></section></div><section class="panel" id="copilot"><h2>AI Copilot</h2><textarea id="q" placeholder="Ex: Pourquoi le service Payment est-il à risque ? Quelles preuves avons-nous ?"></textarea><button onclick="ask()" style="margin-top:10px">Ask Copilot</button><pre id="a" class="muted"></pre></section>{integration_html}</main><script>async function demo(){{let r=await fetch('/api/demo',{{method:'POST'}});document.getElementById('demo').textContent=await r.text();setTimeout(()=>location.reload(),1500)}}async function ask(){{let q=document.getElementById('q').value;let r=await fetch('/api/copilot',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{question:q}})}});document.getElementById('a').textContent=JSON.stringify(await r.json(),null,2)}}</script></body></html>'''
