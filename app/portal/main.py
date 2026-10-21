import os,json,html,uuid,hmac,re
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
@app.post('/api/demo-enriched')
def demo_enriched(authorization:str|None=Header(default=None)):
    """Independent DEMO B launch: evidence richer, but never pre-approve Critic."""
    if os.getenv('AIOPS_DEMO_LAUNCH_ENABLED')!='true':
        raise HTTPException(403,'demo_launch_disabled')
    secret=os.getenv('AIOPS_INTERNAL_TOKEN') or os.getenv('AIOPS_ADMIN_TOKEN')
    bearer=(authorization or '').removeprefix('Bearer ')
    if not secret or not hmac.compare_digest(bearer,secret):
        raise HTTPException(401,'invalid internal token')
    demo_id=uuid.uuid4().hex
    external=f'DEMO-ENRICHED-{demo_id}'
    iid=post_json(CORE,'/api/incidents',{'external_id':external,
        'title':'Synthetic ACME payments SAN degradation — multi-source investigation',
        'severity':'P1','service_id':'ACME-SVC-PAYMENTS','source':'portal-demo-enriched',
        'synthetic':True,'payload':{'scenario_variant':'evidence-enriched','synthetic':True}})['incident_id']
    run=post_json(CORE,'/api/runs',{'mode':'DEMO',
        'scenario_id':'SCN-GOLDEN-PAYMENT-P1','incident_id':iid,
        'idempotency_key':external})
    return post_json(CORE,f"/api/runs/{run['run_id']}/execute",{})

from portal.ui_theme import shell, panel, table, pretty, esc
from portal.twin_graph import graph_panel

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
def timeline_page(run_id:str|None=None, q:str="", status:str="ALL"):
    """Real incident/run selector with event-by-event explanations and AI registers."""
    from portal.timeline_explain import event_box,run_selector,incident_explorer,investigation_overview
    from portal.demo_explain import render_critic_explanation
    from urllib.parse import quote
    items=_runs()
    registry=_get("/api/incidents")
    incidents=registry.get("items",[]) if isinstance(registry.get("items"),list) else []
    # Core returns most recent runs first; do not promote stale RUNNING rows by default.
    selected=run_id or next((str(x.get("run_id")) for x in items if x.get("run_id")),None)
    content='''<style>
    main{max-width:1500px}
    .timeline-ui input,.timeline-ui select{font:inherit;background:var(--card);color:var(--text);border:1px solid var(--line);border-radius:8px;padding:9px;min-width:170px}
    .timeline-ui form{display:flex;flex-wrap:wrap;align-items:end;gap:12px;margin-bottom:16px}
    .timeline-ui label{display:flex;flex-direction:column;gap:5px;font-weight:600}
    .timeline-ui details{margin:10px 0;padding:10px 14px;border:1px solid var(--line);border-radius:10px}
    .timeline-ui summary{cursor:pointer;line-height:1.6}
    .timeline-ui li{padding:4px 0}
    .timeline-ui a[aria-current="page"]{font-weight:700;color:#6560c5}
    .timeline .event{line-height:1.65;font-size:1rem;padding:20px 23px}
    .timeline .event h3{font-size:1.12rem}
    .timeline .event p{margin:8px 0}
    .timeline .event details{margin-top:12px;border-top:1px solid var(--line);padding-top:10px}
    .timeline .event pre{font-size:.85rem;max-height:400px;overflow:auto}
    .investigation-warning{border-left:4px solid #d97706;padding:12px;background:var(--bg)}
    .investigation-steps{display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin-top:16px}
    .investigation-steps a{padding:6px 10px;border:1px solid var(--line);border-radius:8px;text-decoration:none}
    .timeline .event{scroll-margin-top:90px}
    @media(max-width:700px){.timeline{margin-left:6px;padding-left:15px}.timeline .event{padding:13px}}
    </style>'''
    content+=panel("Explorateur des incidents — recherche et filtres",
        '<div class="timeline-ui">'+incident_explorer(items,selected,q,status,incidents=incidents)+'</div>')

    content+=panel("Périmètre et transparence",
        "<p>Les incidents et runs proviennent de Core, y compris les incidents sans exécution. "
        "Les listes sont limitées aux enregistrements renvoyés par Core. Les observations DEMO sont synthétiques ; les décisions IA enregistrées sont réelles.</p>")
    if not selected:
        content+=panel("Timeline","<p>Aucun run accessible depuis Core.</p>")
        return shell("/timeline","Timeline des incidents","Choisir un run pour suivre les événements et décisions.",content)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}",selected):
        raise HTTPException(404,"invalid_run_id")
    match=next((x for x in items if x.get("run_id")==selected),None)
    if not match:
        raise HTTPException(404,"run_not_in_registry")
    key=quote(selected,safe="")
    detail=_get("/api/runs/"+key)
    ledger=_get("/api/runs/"+key+"/ai-ledger")
    events=detail.get("events") if isinstance(detail.get("events"),list) else []
    cards="".join(event_box(e,i) for i,e in enumerate(events,1))
    if not cards:
        cards="<p>Aucun événement disponible depuis Core.</p>"
    content+=panel("Diagnostic et accès rapide",investigation_overview(match,events,incidents))
    content+=panel("Run sélectionné : "+selected,
        '<p><strong>État :</strong> '+esc(match.get("status","INCONNU"))+
        ' · <strong>Mode :</strong> '+esc(match.get("mode","INCONNU"))+
        ' · <a href="/demo-studio/run/'+key+'">Détail Demo Studio (si mode DEMO)</a></p>'
        +'<div class="timeline">'+cards+'</div>')
    if match.get("status") in ("CREATED","RUNNING"):
        content+=panel("Actualisation de l'investigation",
            '<p>Ce run est en cours. Actualisation automatique toutes les 10 secondes ; '
            'aucune action n’est déclenchée.</p>'
            '<script>setTimeout(function(){window.location.reload()},10000)</script>')
    content+=panel("Raisonnement observable — Analyst / Critic",render_critic_explanation(ledger))
    content+=panel("Registres IA et Policy complets",pretty(ledger))
    return shell("/timeline","Timeline des incidents",
        "Historique réel Core, explications étape par étape, succès et blocages compris.",
        content,mode=match.get("mode","INCONNU"))

@app.get("/twin",response_class=HTMLResponse)
def twin_page():
    summary=_get("/api/twin/summary",TWIN)
    graph=_get("/api/twin/graph",TWIN)
    nodes=graph.get("nodes",[]) if isinstance(graph.get("nodes"),list) else []
    edges=graph.get("edges",[]) if isinstance(graph.get("edges"),list) else []
    body=panel("Résumé Digital Twin",pretty(summary))
    impact=_get("/api/twin/impact/ACME-SAN-FABRIC-A",TWIN)
    body+=graph_panel(graph,impact=impact)
    body+=panel("Inventaire des nœuds",table(["ID","Type","Site","État","Santé"],
        [(x.get("node_id"),x.get("type"),x.get("site"),x.get("state"),x.get("health")) for x in nodes[:200]]))
    body+=panel("Relations de dépendance",table(["Source","Relation","Cible"],
        [(x.get("source_id"),x.get("relation_type"),x.get("target_id")) for x in edges[:300]]))
    body+=panel("Impact ACME-SAN-FABRIC-A",pretty(impact))
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

@app.get("/demo-studio",response_class=HTMLResponse)
def demo_studio():
    """Safe read-only ACME storyboard: no launch, effects, or credentials in browser."""
    dashboard=_get("/api/dashboard")
    graph=_get("/api/twin/graph",TWIN)
    impact=_get("/api/twin/impact/ACME-SAN-FABRIC-A",TWIN)
    runs=_runs()
    demo_runs=[r for r in runs if r.get("mode") in ("DEMO","REPLAY","STORY")]
    body=panel("Préflight — qualification en lecture seule",
        '<p><strong>SCÉNARIO ACME CANDIDAT</strong> — cette page n’injecte aucun incident et ne déclenche aucune remédiation. '
        'Les données ci-dessous proviennent des API Core/Twin; les erreurs sont signalées INCONNU.</p>'
        +table(["Contrôle","Résultat"],[
          ("Core /api/dashboard",dashboard.get("status","DONNÉES CONSULTÉES") if dashboard.get("status")!="UNKNOWN" else "INCONNU"),
          ("Digital Twin graph","DISPONIBLE" if isinstance(graph.get("nodes"),list) else "INCONNU"),
          ("Impact SAN-A","DISPONIBLE" if isinstance(impact.get("affected"),list) and impact.get("root") else "INCONNU"),
          ("Scénarios DEMO/REPLAY/STORY visibles",str(len(demo_runs)))
        ]))
    if os.getenv("AIOPS_DEMO_LAUNCH_ENABLED")=="true":
        body+=panel("Lancer le scénario synthétique ACME",
          '<p>Dev uniquement : jeton opérateur saisi localement, jamais conservé dans la page. '
          'Le lancement crée un incident DEMO avec une identité unique et demande son exécution par Core/Temporal.</p>'
          '<label for="operator-token">Jeton interne de la stack de développement</label>'
          '<input id="operator-token" type="password" autocomplete="off" style="width:100%;max-width:440px">'
          '<p><button id="launch-acme" type="button">Lancer la démonstration ACME</button></p>'
          '<p id="launch-status" role="status" aria-live="polite">En attente.</p>'
          '<script>(function(){const b=document.getElementById("launch-acme");'
          'b.addEventListener("click",async()=>{const t=document.getElementById("operator-token");'
          'const status=document.getElementById("launch-status");const token=t.value;t.value="";'
          'if(!token){status.textContent="Jeton requis";return;}b.disabled=true;'
          'status.textContent="Création du run DEMO…";'
          'try{const response=await fetch("/api/demo",{method:"POST",headers:{"Authorization":"Bearer "+token,"Content-Type":"application/json"},body:"{}"});'
          'if(!response.ok){status.textContent="Échec du lancement : HTTP "+response.status;return;}'
          'const data=await response.json();const rid=String(data.run_id||"");'
          'if(!/^[A-Za-z0-9_-]{1,128}$/.test(rid)){status.textContent="Réponse de lancement sans identifiant valide";return;}'
          'location.assign("/demo-studio/run/"+encodeURIComponent(rid));'
          '}catch(e){status.textContent="Core ou portail indisponible";}finally{b.disabled=false;}});})();</script>')
    body+=graph_panel(graph,impact=impact)
    body+=panel("Exécutions de démonstration déjà enregistrées",
      table(["Run","Mode","État","Scénario"],[
       (r.get("run_id","INCONNU"),r.get("mode","INCONNU"),
        r.get("status","INCONNU"),r.get("scenario_id","INCONNU")) for r in demo_runs[:30]]))
    import urllib.parse
    if demo_runs:
        links="".join('<li><a href="/demo-studio/run/'+urllib.parse.quote(str(r.get("run_id","")),safe="")+'">'+esc(r.get("run_id","INCONNU"))+'</a></li>' for r in demo_runs[:30] if re.fullmatch(r"[A-Za-z0-9_-]{1,128}",str(r.get("run_id",""))))
        body+=panel("Ouvrir les traces Analyst/Critic/Policy","<ul>"+links+"</ul>")
    body+=panel("Qualification et prochaines étapes",
      '<p>Le parcours connecté Core → Temporal → Analyst/Critic → Policy → Evidence reste à '
      'valider en stack V2.8 isolée avant de permettre le lancement depuis ce portail.</p>'
      '<p><a href="/timeline">Consulter la timeline</a> · <a href="/qualification">Matrice de qualification</a></p>')
    return shell("/demo-studio","ACME Demo Studio",
      "Démonstration intégrée ACME — lecture des sources Core/Twin et lancement optionnel en mode développement.",
      body,mode="DEVELOPPEMENT DEMO" if os.getenv("AIOPS_DEMO_LAUNCH_ENABLED")=="true" else "LECTURE SEULE")

@app.get("/demo-studio/run/{rid}",response_class=HTMLResponse)
def demo_run_detail(rid:str):
    """Show source-backed demo evidence, never substitute fixtures for live records."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}",rid):
        raise HTTPException(404,"invalid_demo_run_id")
    candidates=_runs()
    matched=next((r for r in candidates if r.get("run_id")==rid and r.get("mode") in ("DEMO","REPLAY","STORY")),None)
    if not matched:
        raise HTTPException(404,"demo_run_not_found")
    from urllib.parse import quote
    key=quote(rid,safe="")
    detail=_get("/api/runs/"+key)
    ledger=_get("/api/runs/"+key+"/ai-ledger")
    gate=_get("/api/runs/"+key+"/gates")
    body=panel("Suivi de l'exécution",
      '<p id="run-watch-status" role="status" aria-live="polite">Rafraîchissement toutes les 5 secondes, jusqu’à un état terminal.</p>'
      '<button type="button" id="run-watch-refresh">Actualiser maintenant</button>'
      '<pre id="run-watch-state" class="log">En attente du premier rafraîchissement.</pre>'
      '<script>(function(){const rid='+json.dumps(rid)+
      ';const state=document.getElementById("run-watch-state");'
      'const status=document.getElementById("run-watch-status");'
      'let active=true;let pending=false;'
      'async function refresh(){if(!active||pending)return;pending=true;'
      'try{const response=await fetch("/api/demo-status/"+encodeURIComponent(rid),{cache:"no-store"});'
      'if(!response.ok){status.textContent="Statut indisponible : HTTP "+response.status;return;}'
      'const result=await response.json();state.textContent=JSON.stringify({run_id:result.run_id,status:result.status,mode:result.mode},null,2);'
      'const trace=document.getElementById("run-watch-trace");'
      'if(trace)trace.textContent=JSON.stringify({events:result.events,ledger:result.ledger,gates:result.gates},null,2);'
      'if(["RESOLVED","BLOCKED","FAILED","CANCELLED"].includes(result.status)){active=false;status.textContent="État terminal. Recharger la page pour voir les derniers registres Analyst/Critic/Policy.";}}'
      'catch(e){status.textContent="Suivi temporairement indisponible";}finally{pending=false;}}'
      'document.getElementById("run-watch-refresh").addEventListener("click",()=>{active=true;refresh();});'
      'refresh();setInterval(refresh,5000);})();</script>')
    body+=panel("Timeline et registres en direct",
      '<p class="muted">Données en lecture seule provenant de Core ; aucune chronologie n’est inventée.</p>'
      '<pre id="run-watch-trace" class="log">Chargement des éléments de preuve…</pre>')
    body+=panel("État canonique du run",pretty(detail))
    events=detail.get("events") if isinstance(detail.get("events"),list) else []
    rows=[(e.get("sequence","?"),e.get("occurred_at","INCONNU"),e.get("stage","INCONNU"),
           e.get("event_type","INCONNU"),e.get("status","INCONNU"),e.get("decision","INCONNU"))
          for e in events if isinstance(e,dict)]
    body+=panel("Timeline canonique des événements",
      table(["Séquence","Date","Étape","Événement","État","Décision"],rows)
      if rows else '<p class="muted">Aucun événement disponible depuis Core.</p>')
    from portal.demo_explain import render_critic_explanation
    body+=panel("Pourquoi le Critic valide ou bloque",render_critic_explanation(ledger))
    body+=panel("Analyst · Critic · Policy (registre)",pretty(ledger))
    body+=panel("Gates et décisions",pretty(gate))
    body+=panel("Traçabilité",'<p>Les données sont lues depuis Core pour le run sélectionné; un registre absent s’affiche INCONNU. '
      'Aucune remédiation, ré-exécution ni approbation n’est disponible ici.</p>')
    return shell("/demo-studio","Démonstration · "+rid,
      "Parcours incident, analyse et décisions depuis le registre Core.",
      body,mode=matched.get("mode","DEMO"))

@app.get("/api/demo-status/{rid}")
def demo_status(rid:str):
    """Read-only polling endpoint with strict DEMO ownership checked against Core."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}",rid):
        raise HTTPException(404,"invalid_run_id")
    allowed=next((r for r in _runs() if r.get("run_id")==rid and r.get("mode") in ("DEMO","REPLAY","STORY")),None)
    if not allowed:
        raise HTTPException(404,"demo_run_not_found")
    detail=_get("/api/runs/"+rid)
    if detail.get("status")=="UNKNOWN":
        return {"run_id":rid,"status":"UNKNOWN","source":"Core unavailable"}
    run=detail.get("run",{}) if isinstance(detail.get("run"),dict) else detail
    ledger=_get("/api/runs/"+rid+"/ai-ledger")
    gates=_get("/api/runs/"+rid+"/gates")
    events=detail.get("events",None)
    if not isinstance(events,list):
        events="INCONNU"
    return {"run_id":rid,"status":run.get("status","UNKNOWN"),"mode":allowed.get("mode"),
            "source":"Core","events":events,"ledger":ledger,"gates":gates}

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
