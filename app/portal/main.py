import os,json,html,uuid,hmac
from fastapi import FastAPI,Request,Header,HTTPException
from fastapi.responses import HTMLResponse,JSONResponse
from shared.http import get_json,post_json
app=FastAPI(title='ACME AioOps Command Center',version='2.0.0')
CORE=os.getenv('CORE_URL','http://aiops2-core:810');COPILOT=os.getenv('COPILOT_URL','http://aiops2-copilot:814');TWIN=os.getenv('TWIN_URL','http://aiops2-twin:811')
@app.get('/health')
def health():return {'status':'ok','component':'portal','external_port':7777,'internal_port':777}
@app.get('/api/portal/bootstrap')
def bootstrap():return {'dashboard':get_json(CORE,'/api/dashboard'),'runs':get_json(CORE,'/api/runs'),'twin':get_json(TWIN,'/api/twin/summary')}
@app.post('/api/copilot')
def copilot(q:dict):return post_json(COPILOT,'/api/copilot/query',q)
@app.post('/api/demo')
def demo(authorization:str|None=Header(default=None)):
    # The disabled browser button is not an authorization boundary.
    if os.getenv('AIOPS_DEMO_LAUNCH_ENABLED')!='true':
        raise HTTPException(403,'demo_launch_disabled')
    secret=os.getenv('AIOPS_INTERNAL_TOKEN') or os.getenv('AIOPS_ADMIN_TOKEN')
    bearer=(authorization or '').removeprefix('Bearer ')
    if not secret or not hmac.compare_digest(bearer,secret):
        raise HTTPException(401,'invalid internal token')
    demo_id=uuid.uuid4().hex
    iid=post_json(CORE,'/api/incidents',{'external_id':f'DEMO-GOLDEN-PAYMENT-{demo_id}','title':'Payment latency following FC fabric degradation','severity':'P1','service_id':'ACME-SVC-PAYMENTS','source':'portal-demo','synthetic':True,'payload':{'seed':20261018}})['incident_id']
    run=post_json(CORE,'/api/runs',{'mode':'DEMO','scenario_id':'SCN-GOLDEN-PAYMENT-P1','incident_id':iid,'idempotency_key':f'DEMO-GOLDEN-PAYMENT-{demo_id}'})
    return post_json(CORE,f"/api/runs/{run['run_id']}/execute",{})
from portal.ui_theme import shell, panel, table, pretty, esc

def _get(path,base=CORE):
    try:
        return get_json(base,path)
    except Exception as exc:
        return {"status":"UNKNOWN","error_type":type(exc).__name__}

def _runs():
    response=_get("/api/runs")
    return response.get("items",[]) if isinstance(response.get("items"),list) else []

def _run_id(r):
    return r.get("run_id","UNKNOWN")

@app.get("/",response_class=HTMLResponse)
def home():
    d=_get("/api/dashboard"); t=_get("/api/twin/summary",TWIN)
    cards=[
        ("Incidents ouverts",d.get("open_incidents"),"#E24B4A"),
        ("P1 ouverts",d.get("open_p1"),"#EF9F27"),
        ("Runs actifs",d.get("running"),"#7F77DD"),
        ("Runs bloqués",d.get("blocked"),"#378ADD"),
        ("Nœuds Twin",t.get("nodes"),"#1D9E75"),
        ("Équipements dégradés",d.get("degraded_nodes"),"#639922"),
    ]
    tiles="".join(
        f'<div class="tile" style="--c:{color}"><strong>{esc("INCONNU" if v is None else v)}</strong><span>{esc(k)}</span></div>'
        for k,v,color in cards
    )
    rows=[(_run_id(r),r.get("mode","UNKNOWN"),r.get("status","UNKNOWN"),r.get("scenario_id","UNKNOWN")) for r in _runs()[:15]]
    content='<section aria-label="Indicateurs" class="kpi">'+tiles+'</section>'
    content+=panel("Runs récents",table(["Run","Mode","État","Scénario"],rows))
    content+=panel("Digital Twin — état courant",pretty(t))
    content+=panel("Démo ACME — simulation uniquement",
        '<p class="muted">La démo crée un incident synthétique. Elle est désactivée sur cette interface tant que la stack complète et sa remise à zéro ne sont pas qualifiées.</p><button disabled title="Qualification nécessaire">Lancer DEMO (non qualifié)</button>')
    return shell("/","Cockpit opérationnel","Vue consolidée des incidents, exécutions et dépendances réelles du registre.",content)

@app.get("/runs",response_class=HTMLResponse)
def runs_page():
    rows=[(_run_id(r),r.get("mode","UNKNOWN"),r.get("status","UNKNOWN"),r.get("overall_confidence","INCONNU"),r.get("scenario_id","UNKNOWN")) for r in _runs()]
    return shell("/runs","Incidents & Runs","Registre canonique et état d'exécution ; les champs absents sont signalés.",panel("Exécutions",table(["Run","Mode","État","Confiance","Scénario"],rows)))

@app.get("/timeline",response_class=HTMLResponse)
def timeline_page():
    items=_runs()
    if not items:
        return shell("/timeline","Timeline incident","Les événements proviennent de Core ; aucun événement de démonstration n'est inventé.",panel("Chronologie",'<p>INCONNU — aucun run accessible.</p>'))
    rid=str(items[0].get("run_id",""))
    if not rid:
        return shell("/timeline","Timeline incident","Événements non disponibles.",panel("Chronologie",'<p>INCONNU — run_id absent.</p>'))
    detail=_get("/api/runs/"+__import__("urllib.parse",fromlist=["quote"]).quote(rid,safe=""))
    events=detail.get("events",[]) if isinstance(detail.get("events"),list) else []
    cards=""
    for e in events:
        status=e.get("status","UNKNOWN")
        color={"PASS":"#1D9E75","BLOCKED":"#E24B4A","FAIL":"#E24B4A","RUNNING":"#EF9F27"}.get(status,"#7F77DD")
        cards+=f'<article class="event" style="--c:{color}"><small>#{esc(e.get("sequence","?"))} · {esc(e.get("stage","UNKNOWN"))} · {esc(e.get("occurred_at","horodatage indisponible"))}</small><h3>{esc(e.get("event_type","UNKNOWN"))}</h3><p>{esc(status)}</p><span class="chip">{esc(e.get("event_key","sans clé"))}</span></article>'
    if not cards: cards='<p>INCONNU — événements non disponibles pour ce run.</p>'
    content=panel("Run sélectionné : "+rid,'<p>Timeline canonique, pas un scénario fictif.</p><div class="timeline">'+cards+'</div>')
    return shell("/timeline","Timeline incident","Chronologie des événements persistés dans Core ; dernier run en tête de liste.",content,mode=items[0].get("mode","INCONNU"))

@app.get("/twin",response_class=HTMLResponse)
def twin_page():
    summary=_get("/api/twin/summary",TWIN)
    graph=_get("/api/twin/graph",TWIN)
    nodes=graph.get("nodes",[]) if isinstance(graph.get("nodes"),list) else []
    edges=graph.get("edges",[]) if isinstance(graph.get("edges"),list) else []
    body=panel("Résumé Digital Twin",pretty(summary))
    body+=panel("Inventaire des nœuds",table(["ID","Type","Site","État","Santé"],
        [(x.get("node_id"),x.get("type"),x.get("site"),x.get("state"),x.get("health")) for x in nodes[:200]]))
    body+=panel("Relations de dépendance",table(["Source","Relation","Cible"],
        [(x.get("source_id"),x.get("relation_type"),x.get("target_id")) for x in edges[:300]]))
    body+=panel("Impact ACME-SAN-FABRIC-A",pretty(_get("/api/twin/impact/ACME-SAN-FABRIC-A",TWIN)))
    return shell("/twin","Digital Twin ACME","Topologie et dépendances observables, distinctes des injections de simulation.",body)

@app.get("/evidence",response_class=HTMLResponse)
def evidence_page():
    body=panel("Traçabilité des preuves",'<p>Les preuves doivent porter provenance, fraîcheur, lien au run et mode SYNTHETIC/LIVE. Aucun indicateur de confiance artificiel n’est produit par cette vue.</p>')
    body+=panel("Point de contrôle",'<p>Consulter les identifiants de preuves dans les événements Core. La liste transversale Evidence exige un adaptateur et un contrôle de droits complémentaires.</p>')
    return shell("/evidence","Preuves & Observabilité","Evidence ledger, liens de causalité et limites d’acquisition.",body)

@app.get("/policy",response_class=HTMLResponse)
def policy_page():
    rows=[(_run_id(r),r.get("status","UNKNOWN"),r.get("mode","UNKNOWN")) for r in _runs() if r.get("status") in ("BLOCKED","WAITING")]
    body=panel("Exécutions bloquées / en attente",table(["Run","État","Mode"],rows))
    body+=panel("Contrôles d'autorisation",'<p>Critic rejeté : blocage atomique, reçu et outbox. Approbation HITL, ownership et fencing sont requis avant effet. Cette page ne crée aucune validation.</p>')
    return shell("/policy","Policy & HITL","Décisions, approbations et barrières de sécurité — lecture seule.",body)

@app.get("/copilot",response_class=HTMLResponse)
def copilot_page():
    body=panel("Assistant IA et contestation",
        '<p>Questionner les incidents, la CMDB, les preuves et les décisions. Les réponses doivent citer leurs sources, confiance et limites.</p>'
        '<label for="q">Votre question</label><textarea id="q" placeholder="Quelles preuves soutiennent le diagnostic ?"></textarea>'
        '<p><button type="button" id="ask">Interroger Copilot</button></p><pre class="log" id="answer" role="status" aria-live="polite">Aucune réponse.</pre>'
        '<script>document.getElementById("ask").addEventListener("click",async function(){const out=document.getElementById("answer");out.textContent="Chargement…";try{const r=await fetch("/api/copilot",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:document.getElementById("q").value})});out.textContent=JSON.stringify(await r.json(),null,2);if(!r.ok)out.textContent="Erreur HTTP "+r.status+" : "+out.textContent;}catch(e){out.textContent="Copilot indisponible";}});</script>')
    return shell("/copilot","Copilot","Conversation contextualisée ; une réponse non étayée ne constitue pas une preuve.",body)

@app.get("/qualification",response_class=HTMLResponse)
def qualification_page():
    checks=[("QF178–179","35 tests unitaires rapportés sur Debian isolée","Rapporté, non CI"),
      ("QF187","HTTP auth 401/401/409","Rapporté sur Debian"),
      ("QF188","Reprise HTTP et idempotence","Rapporté sur Debian"),
      ("QF189","8 requêtes concurrentes, 1 commit","Rapporté sur Debian"),
      ("QF190","Réponse client perdue, rejeu sans doublon","Rapporté sur Debian"),
      ("Temporal E2E","Reprise complète / pas de double appel IA","NON QUALIFIÉ"),
      ("Digital Twin E2E","Injection → analyse → gate → UI","NON QUALIFIÉ"),
      ("LIVE / Production","Critères de sécurité et reprise","NO-GO")]
    return shell("/qualification","Qualification","Provenance explicite des essais, points bloquants et gates de promotion.",
      panel("Matrice de qualification",table(["Campagne","Périmètre","État"],checks))+
      panel("Règle d'audit",'<p>Résultats QF issus des journaux opérateur ; ne pas les présenter comme un succès GitHub Actions sans preuve de workflow.</p>'))
