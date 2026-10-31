import os,json,html
from pathlib import Path
from fastapi import FastAPI,Request,Header,HTTPException,Response
from fastapi.responses import HTMLResponse,JSONResponse,FileResponse
from shared.http import get_json,post_json
from portal.portal_integrations import build_navigation, render_navigation_html
from portal.portal_read_models import read_portal_snapshot
from portal.portal_command_auth import require_demo_operator, require_core_identifier, NO_STORE
from portal.noc_runtime import router as noc_runtime_router, _require_portal_read_auth, _noc_json_response
from portal.noc_correlation import router as noc_correlation_router
from portal.noc_demo_rag import router as noc_demo_rag_router
from portal.noc_grafana_health import router as noc_grafana_health_router
from portal.acme_impact_read_model import router as acme_impact_router
from portal.acme_explore_story import router as acme_explore_story_router
from portal.acme_run_detail import router as acme_run_detail_router
from portal.glpi_operator_view import router as glpi_operator_view_router
from portal.oidc_session import router as oidc_session_router
app=FastAPI(title='ACME AioOps Command Center',version='2.0.0')
@app.middleware('http')
async def portal_security_headers(request: Request, call_next):
    # Cover framework-generated 404/405/422 errors as well as route responses.
    # Preserve the stricter, route-specific CSP on HTML and authenticated APIs.
    response = await call_next(request)
    defaults = {
        'Cache-Control': 'no-store',
        'Pragma': 'no-cache',
        'X-Content-Type-Options': 'nosniff',
        'Referrer-Policy': 'no-referrer',
        'X-Frame-Options': 'DENY',
        'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
    }
    for key, value in defaults.items():
        response.headers.setdefault(key, value)
    return response
app.include_router(noc_runtime_router)
app.include_router(noc_correlation_router)
app.include_router(noc_demo_rag_router)
app.include_router(noc_grafana_health_router)
app.include_router(acme_impact_router)
app.include_router(acme_explore_story_router)
app.include_router(acme_run_detail_router)
app.include_router(glpi_operator_view_router)
app.include_router(oidc_session_router)
CORE=os.getenv('CORE_URL','http://aiops2-core:810');COPILOT=os.getenv('COPILOT_URL','http://aiops2-copilot:814');TWIN=os.getenv('TWIN_URL','http://aiops2-twin:811')
@app.get('/health')
def health():return {'status':'ok','component':'portal','external_port':os.getenv('AIOPS_PORTAL_HOST_PORT','17777'),'internal_port':777}
@app.get('/api/portal/bootstrap')
def bootstrap(authorization: str | None = Header(default=None)):
    # Shared PR #36 NOC viewer token; deny before any Core/Twin network access.
    try:
        _require_portal_read_auth(authorization)
    except HTTPException as exc:
        return _noc_json_response({'detail': exc.detail}, status_code=exc.status_code)
    # The shared viewer bearer is not a tenant/actor authorization. Core's
    # /api/dashboard and /api/runs and Twin's summary lack tenant-scoped
    # contracts. Never fetch or disclose these read models to a browser.
    # Re-enable only after Core supplies server-derived tenant authorization.
    return _noc_json_response({
        'state': 'UNKNOWN',
        'reason': 'TENANT_ACL_NOT_QUALIFIED',
        'connection_state': 'UNKNOWN',
        'source': 'CORE_TWIN_READ_MODELS_NOT_TENANT_AUTHORIZED',
        'source_freshness': 'UNKNOWN',
    }, status_code=503)
@app.get('/assets/portal-bootstrap.js')
def portal_bootstrap_script():
    return FileResponse(Path(__file__).with_name('portal_bootstrap_client.js'),
                        media_type='application/javascript',
                        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

@app.get('/api/portal/components')
def components(authorization: str | None = Header(default=None)):
    # A shared viewer bearer authenticates but cannot authorize disclosure
    # of operator-configured GLPI/NOC URLs or tenant-specific navigation.
    # Do not read the registry or environment links before server-derived ACL.
    try:
        _require_portal_read_auth(authorization)
    except HTTPException as exc:
        return _noc_json_response({'detail': exc.detail}, status_code=exc.status_code)
    return _noc_json_response({
        'state': 'UNKNOWN',
        'reason': 'TENANT_ACL_NOT_QUALIFIED',
        'connection_state': 'UNKNOWN',
        'source': 'PORTAL_NAVIGATION_NOT_TENANT_AUTHORIZED',
        'source_freshness': 'UNKNOWN',
        'tenant_acl_qualified': False,
    }, status_code=503)

@app.get('/assets/portal-navigation.js')
def portal_navigation_script():
    return FileResponse(Path(__file__).with_name('portal_navigation_client.js'),
                        media_type='application/javascript',
                        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

@app.post('/api/copilot')
def copilot(authorization: str | None = Header(default=None)):
    # Do not bind or parse a browser request body: FastAPI would otherwise
    # return 422 for malformed JSON before the auth gate runs. No body is
    # consumed, forwarded or treated as actor/tenant authority.
    # Legacy Copilot has no tenant/run-scoped read contract. A shared viewer
    # bearer cannot authorize sending browser questions to this upstream.
    try:
        _require_portal_read_auth(authorization)
    except HTTPException as exc:
        return _noc_json_response({'detail': exc.detail}, status_code=exc.status_code)
    return _noc_json_response({
        'state': 'UNKNOWN',
        'reason': 'TENANT_ACL_NOT_QUALIFIED',
        'connection_state': 'UNKNOWN',
        'source': 'COPILOT_NOT_TENANT_AUTHORIZED',
        'source_freshness': 'UNKNOWN',
    }, status_code=503)
@app.post('/api/demo')
def demo(authorization: str | None = Header(default=None)):
    # A browser-supplied operator bearer authenticates only a DEMO request.
    # It cannot supply the actor/tenant/Run authorization required for Core
    # incident creation, Run creation or execution. Refuse before any I/O.
    try:
        require_demo_operator(authorization)
    except HTTPException as exc:
        response = _noc_json_response({'detail': exc.detail}, status_code=exc.status_code)
        response.headers.update(exc.headers or {})
        return response
    return _noc_json_response({
        'state': 'UNKNOWN',
        'reason': 'TENANT_ACL_NOT_QUALIFIED',
        'connection_state': 'UNKNOWN',
        'source': 'DEMO_CORE_MUTATION_NOT_AUTHORIZED',
        'source_freshness': 'UNKNOWN',
        'live_remediation_authorized': False,
    }, status_code=503)
@app.get('/',response_class=HTMLResponse)
def home(response: Response = None):
    # Keep direct callers of the existing home() renderer compatible.
    # FastAPI injects Response on HTTP requests; only then attach headers.
    if response is not None:
        response.headers.update({
            'Cache-Control': 'no-store',
            'Pragma': 'no-cache',
            'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer',
            'X-Frame-Options': 'DENY',
            'Content-Security-Policy': (
                "default-src 'none'; script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
                "img-src 'self' data:; base-uri 'none'; object-src 'none'; "
                "form-action 'self'; frame-ancestors 'none'"
            ),
        })
    # Anonymous shell: no Core/Twin calls and no unverified incident/run data.
    snapshot={'dashboard':None,'runs':None,'twin':None,
              'states':{'dashboard':'UNKNOWN','runs':'UNKNOWN','twin':'UNKNOWN'}}
    d=snapshot['dashboard'] or {};runs=(snapshot['runs'] or {}).get('items',[]);t=snapshot['twin'] or {'state':'UNKNOWN'}
    read_model_status=html.escape(json.dumps(snapshot['states'],sort_keys=True))
    # Never serialize operator-configured integration URLs in anonymous HTML.
    integration_html=render_navigation_html(build_navigation(env={}))
    cards=[('Open P1',d.get('open_p1','UNKNOWN')),('Incidents',d.get('open_incidents','UNKNOWN')),('Running',d.get('running','UNKNOWN')),('Blocked',d.get('blocked','UNKNOWN')),('Twin nodes',d.get('twin_nodes','UNKNOWN')),('Degraded',d.get('degraded_nodes','UNKNOWN'))]
    cards_html=''.join(f'<div class="card"><span>{html.escape(str(k))}</span><strong data-metric="{key}">{html.escape(str(v))}</strong></div>' for (k,v),key in zip(cards,('open_p1','open_incidents','running','blocked','twin_nodes','degraded_nodes')))
    rows=''.join(f'<tr><td><code>{html.escape(str(r["run_id"]))}</code></td><td>{html.escape(str(r.get("mode","UNKNOWN")),quote=True)}</td><td><b>{html.escape(str(r.get("status","UNKNOWN")),quote=True)}</b></td><td>{html.escape(str(r.get("overall_confidence","UNKNOWN")),quote=True)}</td><td>{html.escape(str(r.get("scenario_id","UNKNOWN")),quote=True)}</td></tr>' for r in runs[:15]) or '<tr><td colspan="5">UNKNOWN — aucun run</td></tr>'
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>ACME AioOps</title><style>
body{{margin:0;background:#07111d;color:#e9f2f8;font:14px system-ui,Segoe UI,sans-serif}}header{{position:sticky;top:0;background:#0b1c2b;border-bottom:1px solid #25445a;padding:16px 28px;display:flex;justify-content:space-between;z-index:2}}main{{max-width:1500px;margin:auto;padding:26px}}h1{{font-size:34px;margin:0 0 6px}}h2{{margin-top:30px}}.muted{{color:#8fa7b8}}.grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}}.card{{background:#0d2031;border:1px solid #23445b;border-radius:14px;padding:15px;min-height:78px}}.card span{{display:block;color:#9eb5c5;font-size:12px}}.card strong{{display:block;font-size:30px;margin-top:9px}}.two{{display:grid;grid-template-columns:2fr 1fr;gap:16px}}.panel{{background:#0c1d2d;border:1px solid #23445b;border-radius:14px;padding:18px;margin-top:16px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #1d394e;text-align:left}}button{{border:0;border-radius:9px;padding:11px 15px;background:#2188c7;color:#fff;cursor:pointer;margin-right:8px}}button.secondary{{background:#18384e}}textarea{{width:100%;min-height:80px;background:#07131f;color:#fff;border:1px solid #2a4b61;border-radius:9px;padding:10px;box-sizing:border-box}}pre{{white-space:pre-wrap}}code{{color:#b8d8eb}}a{{color:#8fd0ff}}nav a{{margin-left:8px}}@media(max-width:1100px){{.grid{{grid-template-columns:repeat(3,1fr)}}.two{{grid-template-columns:1fr}}}}@media(max-width:650px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><header><b>ACME AioOps 2.0</b><nav><a href="#runs">Runs</a> · <a href="/itsm">GLPI / ITSM</a> · <a href="#twin">Twin</a> · <a href="/demo/acme-impact">ACME Impact (simulation)</a> · <a href="/demo/explore-story">Explore / Story (simulation)</a> · <a href="#copilot">Copilot</a> · <a href="#noc">NOC</a> · <a href="#integrations">Intégrations</a></nav></header><main><h1>Operations Command Center</h1><div class="muted">Synthetic/demo data is explicitly labelled. Unsupported claims remain UNKNOWN.</div><p class="muted">Read models (non attestés) : <span id="portal-states">{read_model_status}</span></p><div class="panel"><label for="portal-read-token">Jeton lecture Core/Twin (usage unique)</label> <input id="portal-read-token" type="password" autocomplete="off" style="background:#07131f;color:#fff;padding:10px"> <button onclick="loadPortalReadModel()">Charger Core/Twin</button><button class="secondary" onclick="clearPortalReadModel()">Effacer</button><span id="portal-read-result" class="muted">UNKNOWN — accès non authentifié</span></div><div class="panel"><label for="run-detail-id">Run Core (identifiant explicite, sans substitution)</label> <input id="run-detail-id" autocomplete="off" placeholder="RUN-..." style="background:#07131f;color:#fff;padding:10px"> <button type="button" id="run-detail-open">Ouvrir le détail Run</button> <span id="run-detail-error" class="muted">UNKNOWN — lecture authentifiée requise; aucune preuve sans Core</span></div><div class="grid" style="margin-top:20px">{cards_html}</div><div class="panel"><label for="demo-token">Jeton opérateur DEMO (usage unique)</label><input id="demo-token" type="password" disabled aria-disabled="true" autocomplete="off" style="margin:8px;background:#07131f;color:#fff;border:1px solid #2a4b61;padding:10px"><button type="button" disabled aria-disabled="true" title="ACL acteur et tenant non qualifiée">Golden DEMO — désactivé</button><button class="secondary" onclick="location.reload()">Refresh</button><span id="demo" class="muted"></span></div><div class="two"><section class="panel" id="runs"><h2>Canonical Runs</h2><table><tr><th>Run</th><th>Mode</th><th>Status</th><th>Confidence</th><th>Scenario</th></tr><tbody id="portal-runs">{rows}</tbody></table></section><section class="panel" id="twin"><h2>Digital Twin</h2><pre id="portal-twin">{html.escape(json.dumps(t,indent=2,default=str))}</pre></section></div><section class="panel" id="copilot"><h2>AI Copilot</h2><textarea id="q" placeholder="Ex: Pourquoi le service Payment est-il à risque ? Quelles preuves avons-nous ?"></textarea><button onclick="ask()" style="margin-top:10px">Ask Copilot</button><pre id="a" class="muted"></pre></section><section class="panel" id="noc"><h2>NOC — Checkmk / Thruk</h2><p class="muted">Source runtime : UNKNOWN tant qu'aucun fournisseur de read-model signé n'est configuré et vérifié. Le flux de corrélation Incident/Run reste en lecture seule ; aucune preuve LIVE n'est déduite de cette page.</p><p>Contrat API : <code>GET /api/noc/runtime-state</code> (jeton opérateur obligatoire, HMAC SHA-256 et contrôle de fraîcheur). Les liens Thruk et Grafana configurés figurent dans les intégrations ci-dessous.</p><p><code>GET /api/noc/correlation</code> : rapprochement signé NOC / Run canonique, lecture seule et non attesté.</p><label for="noc-token">Jeton opérateur NOC (non enregistré)</label><input id="noc-token" type="password" autocomplete="off" style="margin:8px;background:#07131f;color:#fff;border:1px solid #2a4b61;padding:10px"><button onclick="correlateNoc()">Lire la corrélation</button><pre id="noc-result" class="muted">UNKNOWN — aucune corrélation vérifiée</pre><p><b>Grafana réel — contrôle HTTP uniquement</b> : ne prouve ni métriques Checkmk/Thruk ni droits tenant. <button onclick="grafanaHealth()">Tester Grafana réel (HTTP)</button><pre id="noc-grafana-result" class="muted">NOT_TESTED — service non interrogé</pre></p><p><b>RAG DEMO — fiches synthétiques de PR #36</b> : citations de référence uniquement, ni observation Checkmk, ni inférence IA, ni procédure LIVE.</p><label for="noc-asset">Équipement fictif</label><input id="noc-asset" value="brocade-fc01" autocomplete="off" style="margin:8px;background:#07131f;color:#fff;border:1px solid #2a4b61;padding:10px"><button onclick="demoRag()">Lire fiches RAG DEMO</button><pre id="noc-rag-result" class="muted">UNKNOWN — aucune fiche sélectionnée</pre></section>{integration_html}<section class="panel"><label for="portal-navigation-token">Jeton lecture des liens (usage unique)</label> <input id="portal-navigation-token" type="password" autocomplete="off" style="background:#07131f;color:#fff;padding:10px"> <button onclick="loadPortalNavigation()">Afficher les liens configurés</button><button class="secondary" onclick="clearPortalNavigation()">Effacer les liens</button><span id="portal-navigation-status" class="muted">UNKNOWN — liens non chargés</span></section></main><script src="/assets/portal-navigation.js" defer></script><script src="/assets/portal-bootstrap.js" defer></script><script src="/assets/portal-run-link.js" defer></script><script>async function demo(){{let el=document.getElementById('demo-token');let token=el.value;el.value='';let out=document.getElementById('demo');out.textContent='UNKNOWN — demande en cours';if(!token){{out.textContent='UNKNOWN — jeton opérateur requis';return}}try{{let r=await fetch('/api/demo',{{method:'POST',headers:{{Authorization:'Bearer '+token}},credentials:'omit',cache:'no-store',redirect:'error'}});out.textContent=r.status===202?'DEMO_SUBMITTED_UNVERIFIED — aucune preuve LIVE':'UNKNOWN — commande refusée';}}catch(e){{out.textContent='UNKNOWN — service indisponible'}}}}async function ask(){{let out=document.getElementById('a');out.textContent='UNKNOWN — lecture non qualifiée';try{{let r=await fetch('/api/copilot',{{method:'POST',headers:{{'Content-Type':'application/json'}},credentials:'omit',cache:'no-store',redirect:'error',body:JSON.stringify({{question:document.getElementById('q').value}})}});let data=await r.json();out.textContent='HTTP '+r.status+' — '+(r.status===401||r.status===403?'UNAUTHORIZED':'UNKNOWN')+' — '+String(data.reason||data.detail||'Copilot indisponible')}}catch(e){{out.textContent='UNKNOWN — Copilot indisponible'}}}}function portalNocStatus(r){{return (r.status===401||r.status===403?'UNAUTHORIZED':'UNKNOWN')+' (HTTP '+r.status+') — lecture non qualifiée ou refusée'}}
const portalNocGeneration={{correlation:0,grafana:0,rag:0}};
async function correlateNoc(){{const generation=++portalNocGeneration.correlation;let el=document.getElementById('noc-token');let token=el.value;el.value='';let out=document.getElementById('noc-result');out.textContent='UNKNOWN — lecture en cours';if(!token){{out.textContent='UNKNOWN — jeton opérateur requis';return}}try{{let r=await fetch('/api/noc/correlation',{{headers:{{Authorization:'Bearer '+token}},credentials:'omit',cache:'no-store',redirect:'error'}});let data=await r.json();if(generation!==portalNocGeneration.correlation)return;out.textContent=r.ok&&data&&data.tenant_acl_qualified===true&&data.state!=='UNKNOWN'?JSON.stringify(data,null,2):portalNocStatus(r)}}catch(e){{if(generation!==portalNocGeneration.correlation)return;out.textContent='UNKNOWN — service indisponible'}}}}
async function grafanaHealth(){{const generation=++portalNocGeneration.grafana;let el=document.getElementById('noc-token');let token=el.value;el.value='';let out=document.getElementById('noc-grafana-result');out.textContent='UNKNOWN — lecture en cours';if(!token){{out.textContent='UNKNOWN — jeton opérateur requis';return}}try{{let r=await fetch('/api/noc/grafana-health',{{headers:{{Authorization:'Bearer '+token}},credentials:'omit',cache:'no-store',redirect:'error'}});let data=await r.json();if(generation!==portalNocGeneration.grafana)return;out.textContent=r.ok&&data&&data.tenant_acl_qualified===true&&data.state!=='UNKNOWN'?JSON.stringify(data,null,2):portalNocStatus(r)}}catch(e){{if(generation!==portalNocGeneration.grafana)return;out.textContent='UNKNOWN — Grafana indisponible'}}}}
async function demoRag(){{const generation=++portalNocGeneration.rag;let el=document.getElementById('noc-token');let token=el.value;el.value='';let out=document.getElementById('noc-rag-result');let asset=document.getElementById('noc-asset').value;out.textContent='UNKNOWN — lecture en cours';if(!token){{out.textContent='UNKNOWN — jeton opérateur requis';return}}try{{let r=await fetch('/api/noc/demo-rag?asset='+encodeURIComponent(asset),{{headers:{{Authorization:'Bearer '+token}},credentials:'omit',cache:'no-store',redirect:'error'}});let data=await r.json();if(generation!==portalNocGeneration.rag)return;out.textContent=r.ok&&data&&data.state==='SYNTHETIC_REFERENCE_ONLY'&&data.data_classification==='SYNTHETIC_SIMULATION_ONLY'&&data.tenant_acl_qualified===false&&data.source_runtime_observed===false&&data.runtime_authenticated===false&&data.live_remediation_authorized===false?'SYNTHETIC — '+JSON.stringify(data,null,2):portalNocStatus(r)}}catch(e){{if(generation!==portalNocGeneration.rag)return;out.textContent='UNKNOWN — catalogue indisponible'}}}}
</script></body></html>'''
