import os,json,html,uuid,hmac,re
from fastapi import FastAPI,Request,Header,HTTPException
from fastapi.responses import HTMLResponse,JSONResponse
from shared.http import get_json,post_json
from portal.demo_ledger_read import router as demo_ledger_router
app=FastAPI(title='ACME AioOps Command Center',version='2.0.0')
CORE=os.getenv('CORE_URL','http://aiops2-core:810');COPILOT=os.getenv('COPILOT_URL','http://aiops2-copilot:814');TWIN=os.getenv('TWIN_URL','http://aiops2-twin:811')
app.include_router(demo_ledger_router)
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
from portal.demo_v2 import render_stage_marker_warning

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


def _qualified_demo_runs(rows):
    """Only unambiguous Core DEMO identities may become navigation targets."""
    counts = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("run_id"), str):
            rid = row["run_id"]
            counts[rid] = counts.get(rid, 0) + 1
    return [row for row in rows if isinstance(row, dict)
            and row.get("mode") in ("DEMO", "REPLAY", "STORY")
            and isinstance(row.get("run_id"), str)
            and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", row["run_id"])
            and counts[row["run_id"]] == 1]

def _core_detail_matches_listed_run(detail, listed):
    """Do not display another Core run's events, gates or evidence.

    Inventory identity is a navigation hint, not proof that a later Core
    detail response belongs to the same DEMO/REPLAY/STORY run.
    """
    if not isinstance(detail, dict) or not isinstance(listed, dict):
        return False
    run = detail.get("run")
    if not isinstance(run, dict):
        return False
    if run.get("run_id") != listed.get("run_id"):
        return False
    if run.get("mode") != listed.get("mode") or run.get("mode") not in ("DEMO", "REPLAY", "STORY"):
        return False
    for field in ("incident_id", "scenario_id"):
        expected = listed.get(field)
        if expected is not None and run.get(field) != expected:
            return False
    return True

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
    content+=panel("Démo ACME — valeur métier",
        '<p>Parcours guidé ACME SAN → Payments en six écrans, entièrement illustratif et sans effet LIVE.</p>'
        '<p><a href="/demo-studio/business-story">Ouvrir la démo ACME — valeur métier</a></p>')
    content+=panel("Démo ACME — simulation uniquement",
        '<p class="muted">La démo crée un incident synthétique. Elle est désactivée sur cette interface tant que la stack complète et sa remise à zéro ne sont pas qualifiées.</p><button disabled title="Qualification nécessaire">Lancer DEMO (non qualifié)</button>')
    return shell("/","Cockpit opérationnel","Vue consolidée des incidents, exécutions et dépendances réelles du registre.",content)

@app.get("/runs",response_class=HTMLResponse)
def runs_page():
    runs=_runs()
    rows=[(_run_id(r),r.get("mode","UNKNOWN"),r.get("status","UNKNOWN"),r.get("overall_confidence","INCONNU"),r.get("scenario_id","UNKNOWN")) for r in runs if isinstance(r,dict)]
    # The registry table is escaped by table(); deep links need validated IDs.
    # Never link LIVE, invalid or ambiguous run identities into a DEMO detail.
    from urllib.parse import quote
    eligible=_qualified_demo_runs(runs)
    links="".join(
        '<li><a href="/demo-studio/run/'+quote(row["run_id"],safe="")+'">'+esc(row["run_id"])+'</a>'
        ' · <a href="/timeline?run_id='+quote(row["run_id"],safe="")+'">Timeline</a>'
        ' · '+esc(row.get("status") or "UNKNOWN")+'</li>'
        for row in eligible
    )
    body=panel("Exécutions",table(["Run","Mode","État","Confiance","Scénario"],rows))
    body+=panel("Explorer un run DEMO / REPLAY / STORY — inventaire Core, non attesté",
        "<ul>"+links+"</ul>" if links else "<p>UNKNOWN — aucun run DEMO non ambigu accessible.</p>")
    return shell("/runs","Incidents & Runs","Registre canonique et état d'exécution ; les champs absents sont signalés.",body)

@app.get("/timeline",response_class=HTMLResponse)
def timeline_page(run_id:str|None=None, q:str="", status:str="ALL"):
    """Real incident/run selector with event-by-event explanations and AI registers."""
    from portal.timeline_explain import event_box,run_selector,incident_explorer,investigation_overview,evidence_catalog
    from portal.demo_explain import render_critic_explanation
    from urllib.parse import quote
    items=_runs()
    registry=_get("/api/incidents")
    incidents=registry.get("items",[]) if isinstance(registry.get("items"),list) else []
    # A default DEMO journey must not land on a stale RUNNING or LIVE row.
    # Reject ambiguous IDs rather than selecting one of two conflicting Core rows.
    eligible=_qualified_demo_runs(items)
    preferred=next((r["run_id"] for r in eligible
                    if r.get("status") in ("BLOCKED","RESOLVED")),None)
    selected=run_id or preferred or (eligible[0]["run_id"] if eligible else None)
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
        content+=panel("Timeline","<p>UNKNOWN — aucun run DEMO / REPLAY / STORY non ambigu accessible depuis Core.</p>")
        return shell("/timeline","Timeline des incidents","Choisir un run pour suivre les événements et décisions.",content)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}",selected):
        raise HTTPException(404,"invalid_run_id")
    match=next((x for x in eligible if x["run_id"]==selected),None)
    if not match:
        raise HTTPException(404,"run_not_in_registry")
    key=quote(selected,safe="")
    detail=_get("/api/runs/"+key)
    if not _core_detail_matches_listed_run(detail, match):
        content+=panel("Timeline Core — UNKNOWN",
            "<p>Identité du détail Core non concordante avec l'inventaire DEMO. "
            "Aucun événement, diagnostic ou Evidence n'est présenté.</p>")
        return shell("/timeline", "Timeline des incidents",
                     "Identité Core non qualifiée — lecture seule.", content, mode="UNKNOWN")
    ledger={"status":"UNKNOWN","reason":"viewer_authorization_required"}
    evidence_response=_get("/api/runs/"+key+"/evidence")
    evidence_items=evidence_response.get("items",[]) if isinstance(evidence_response.get("items"),list) else []
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
            '<p>Core déclare ce run en cours ; fraîcheur UNKNOWN sans horodatage vérifié. '
            'Actualisation en lecture seule toutes les 10 secondes ; aucune action n’est déclenchée.</p>'
            '<script>setTimeout(function(){window.location.reload()},10000)</script>')
    content+=panel("Registre des preuves liées — provenance vérifiable",evidence_catalog(evidence_items))
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
    demo_runs=[r for r in runs if isinstance(r,dict) and r.get("mode") in ("DEMO","REPLAY","STORY")]
    body=panel("Démo ACME — valeur métier",
        '<p>Six étapes dans le portail existant : enjeu Payments, incident SAN, diagnostic, décision SIMULATE/HITL et valeur hypothétique. Aucune action LIVE ni gain mesuré.</p>'
        '<p><a href="/demo-studio/business-story">Ouvrir la démo ACME — valeur métier</a></p>')
    body+=panel("Préflight — qualification en lecture seule",
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
    # Navigate a real Core inventory entry; never substitute a fixture or LIVE run.
    import urllib.parse
    eligible=_qualified_demo_runs(runs)
    selected=next((r for r in eligible if r.get("status") in ("RESOLVED","BLOCKED")),
                  eligible[0] if eligible else None)
    if selected:
        rid=urllib.parse.quote(selected["run_id"],safe="")
        run_entry=('<p><strong>Run Core proposé (non attesté) :</strong> '
                   +esc(selected["run_id"])+' · '+esc(selected.get("status","UNKNOWN"))
                   +' · <a href="/demo-studio/run/'+rid+'">Détail Analyst/Critic</a>'
                   +' · <a href="/timeline?run_id='+rid+'">Timeline du même run</a></p>')
    else:
        run_entry='<p><strong>UNKNOWN</strong> — aucun run DEMO/REPLAY/STORY valide accessible depuis Core.</p>'
    # Only correlate the incident explicitly referenced by this Core run inventory row.
    # A missing or ambiguous incident must not become a fabricated Payments impact.
    incident_entry='<p><strong>Incident Core associé :</strong> UNKNOWN — identité ou état non qualifié.</p>'
    if selected:
        incident_id=selected.get("incident_id")
        if isinstance(incident_id,str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}",incident_id):
            incident_registry=_get("/api/incidents")
            records=incident_registry.get("items") if isinstance(incident_registry,dict) else None
            matches=[item for item in records if isinstance(item,dict) and item.get("incident_id")==incident_id] if isinstance(records,list) else []
            if len(matches)==1:
                incident=matches[0]
                incident_entry=('<p><strong>Incident Core associé (inventaire, non attesté) :</strong> '
                    +esc(incident_id)+' · '+esc(incident.get("title") or "UNKNOWN")
                    +' · sévérité '+esc(incident.get("severity") or "UNKNOWN")
                    +' · état incident '+esc(incident.get("state") or "UNKNOWN")
                    +'. Corrélation SAN → Payments : UNKNOWN sans arêtes sourcées.</p>')
    body+=panel("Parcours opérationnel ACME — navigation guidée",
        '<ol><li><a href="/">Cockpit NOC / enjeu Payments</a></li>'
        '<li><a href="/runs">Registre Core des runs</a></li>'
        '<li><a href="/twin">SAN et dépendances Twin</a> — impact Payments à confirmer</li>'
        '<li><a href="/timeline">Investigation Core et Analyst/Critic</a></li>'
        '<li>Ticket ITSM GLPI : <strong>UNKNOWN</strong> — aucune liaison de ticket attestée '
        '(<a href="/acme-stories">contexte métier</a>)</li>'
        '<li><a href="/policy-control">Policy SIMULATE / HITL</a> — aucune approbation réelle présumée</li>'
        '<li><a href="/evidence">Evidence et provenance</a> — aucune remédiation LIVE</li></ol>'
        +run_entry+incident_entry)
    body+=graph_panel(graph,impact=impact)
    body+=panel("Exécutions de démonstration déjà enregistrées",
      table(["Run","Mode","État","Scénario"],[
       (r.get("run_id","INCONNU"),r.get("mode","INCONNU"),
        r.get("status","INCONNU"),r.get("scenario_id","INCONNU")) for r in demo_runs[:30]]))
    import urllib.parse
    if eligible:
        links="".join('<li><a href="/demo-studio/run/'+urllib.parse.quote(r["run_id"],safe="")+'">'+esc(r["run_id"])+'</a></li>' for r in eligible[:30])
        body+=panel("Ouvrir les traces Analyst/Critic/Policy","<ul>"+links+"</ul>")
    body+=panel("Qualification et prochaines étapes",
      '<p>Le parcours connecté Core → Temporal → Analyst/Critic → Policy → Evidence reste à '
      'valider en stack V2.8 isolée avant de permettre le lancement depuis ce portail.</p>'
      '<p><a href="/timeline">Consulter la timeline</a> · <a href="/qualification">Matrice de qualification</a></p>')
    return shell("/demo-studio","ACME Demo Studio",
      "Démonstration intégrée ACME — lecture des sources Core/Twin et lancement optionnel en mode développement.",
      body,mode="DEVELOPPEMENT DEMO" if os.getenv("AIOPS_DEMO_LAUNCH_ENABLED")=="true" else "LECTURE SEULE")

@app.get("/demo-studio/business-story",response_class=HTMLResponse)
def demo_business_story():
    """Read-only ACME story in the existing portal shell; no external requests."""
    from portal.acme_stories import get_story
    story = get_story("PAYMENTS_SAN")
    if not story:
        return HTMLResponse(shell("/demo-studio", "ACME Payments", "Catalogue indisponible",
            panel("UNKNOWN", "<p>Scénario absent.</p>"), mode="UNKNOWN / READ-ONLY"))
    steps = [
        ("Risque Payments", story["business_impact"], "/", "Cockpit NOC"),
        ("Incident SAN", story["symptom"] + " — scénario, pas une mesure observée.",
         "/timeline", "Incidents et runs Core"),
        ("Impact Twin", "ACME-SAN-FABRIC-A → Payments : dépendance à confirmer par des arêtes sourcées.",
         "/twin", "Dépendances Digital Twin"),
        ("Analyst / Critic", "Hypothèse IA et critique à lire sur le même run Core ; aucune décision IA attestée par ce récit.",
         "/timeline", "Investigation Core"),
        ("ITSM GLPI / Policy SIMULATE / HITL",
         "Ticket GLPI : UNKNOWN. Décision SIMULATE et approbation HITL : UNKNOWN tant que les registres authentifiés ne sont pas consultés. Aucun LIVE.",
         "/policy-control", "Contrôles Policy"),
        ("Evidence et valeur",
         "Références evidence_ids : UNKNOWN ici. Avant/après : PROJECTED_ONLY, non mesuré ; bénéfices hypothétiques et rollback non exécuté.",
         "/evidence", "Preuves disponibles"),
    ]
    nav = '<nav aria-label="Étapes ACME"><ol>' + "".join(
        f'<li><a href="#acme-step-{i}">{i}. {esc(title)}</a></li>'
        for i, (title, _, _, _) in enumerate(steps, 1)) + "</ol></nav>"
    body = panel("ACME SAN → Payments — scénario guidé",
        "<p><strong>SIMULATED</strong> : récit explicatif, pas un run observé. "
        "<strong>UNKNOWN</strong> : données non attestées. "
        "<strong>SOURCE-VERIFIED</strong> : réservé aux références contrôlées dans les écrans opérationnels. "
        "Aucun ticket GLPI, effet LIVE, métrique ou preuve n'est fabriqué.</p>" + nav)
    for i, (title, description, href, label) in enumerate(steps, 1):
        body += f'<section id="acme-step-{i}">' + panel(
            f"{i}/6 · {title}",
            "<p><strong>SIMULATED / UNKNOWN</strong> — " + esc(description) + "</p>"
            + '<p><a href="' + esc(href) + '">' + esc(label)
            + " (lecture seule, statut à vérifier)</a></p>") + "</section>"
    body += panel("Continuer dans AIOps2",
        '<p><a href="/demo-studio">Demo Studio V2 et runs existants</a> · '
        '<a href="/acme-stories">Catalogue ACME</a> · '
        '<a href="/qualification">Qualification et limites</a></p>')
    return HTMLResponse(shell("/demo-studio", "ACME Payments — parcours métier",
        "Six étapes explicatives reliées aux écrans opérationnels existants.",
        body, mode="SIMULATED / READ-ONLY"))

@app.get("/demo-studio/run/{rid}",response_class=HTMLResponse)
def demo_run_detail(rid:str):
    """Show source-backed demo evidence, never substitute fixtures for live records."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}",rid):
        raise HTTPException(404,"invalid_demo_run_id")
    candidates=_runs()
    matched=next((r for r in _qualified_demo_runs(candidates) if r["run_id"]==rid),None)
    if not matched:
        raise HTTPException(404,"demo_run_not_found")
    from urllib.parse import quote
    key=quote(rid,safe="")
    detail=_get("/api/runs/"+key)
    if not _core_detail_matches_listed_run(detail, matched):
        return HTMLResponse(shell("/demo-studio", "Run Core — UNKNOWN",
            "Détail Core non concordant avec l'inventaire DEMO.",
            panel("UNKNOWN — identité non qualifiée",
                  "<p>Événements, Analyst/Critic, Policy et Evidence masqués : "
                  "identité Core absente ou contradictoire.</p>"),
            mode="UNKNOWN / READ-ONLY"), status_code=503)
    ledger={"status":"UNKNOWN","reason":"viewer_authorization_required"}
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
    body+=render_stage_marker_warning(detail)
    events=detail.get("events") if isinstance(detail.get("events"),list) else []
    rows=[(e.get("sequence","?"),e.get("occurred_at","INCONNU"),e.get("stage","INCONNU"),
           e.get("event_type","INCONNU"),e.get("status","INCONNU"),e.get("decision","INCONNU"))
          for e in events if isinstance(e,dict)]
    body+=panel("Timeline canonique des événements",
      table(["Séquence","Date","Étape","Événement","État","Décision"],rows)
      if rows else '<p class="muted">Aucun événement disponible depuis Core.</p>')
    from portal.demo_explain import render_critic_explanation
    body+=panel("Pourquoi le Critic valide ou bloque",render_critic_explanation(ledger))
    body+=panel("Registre IA autorisé — lecture seule",
      '<p>Le registre Core est protégé. Jeton viewer distinct du jeton interne ; '
      'aucune décision ni métrique LIVE n’est attestée ici.</p>'
      '<label for="demo-ledger-viewer">Jeton viewer (jamais conservé)</label>'
      '<input id="demo-ledger-viewer" type="password" autocomplete="off">'
      '<button id="demo-ledger-read" type="button">Lire le registre IA</button>'
      '<pre id="demo-ledger-output" class="log" role="status">INCONNU — autorisation requise.</pre>'
      '<script>(function(){const rid='+json.dumps(rid)+
      ';const input=document.getElementById("demo-ledger-viewer");'
      'const output=document.getElementById("demo-ledger-output");'
      'document.getElementById("demo-ledger-read").addEventListener("click",async function(){'
      'const token=input.value;input.value="";output.textContent="Lecture en cours…";'
      'if(!token){output.textContent="INCONNU — jeton viewer requis.";return;}'
      'try{const response=await fetch("/api/demo-studio/runs/"+encodeURIComponent(rid)+"/ai-ledger",'
      '{headers:{"Authorization":"Bearer "+token},cache:"no-store",credentials:"omit"});'
      'if(!response.ok){output.textContent="INCONNU — lecture refusée (HTTP "+response.status+").";return;}'
      'const data=await response.json();'
      'if(data.schema!=="aiops.demo-ledger-read.v1"||data.run_id!==rid||data.runtime_attested!==false)'
      '{output.textContent="INCONNU — contrat invalide.";return;}'
      'output.textContent=JSON.stringify(data,null,2);'
      '}catch(e){output.textContent="INCONNU — registre indisponible.";}});})();</script>')
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
    allowed=next((r for r in _qualified_demo_runs(_runs()) if r["run_id"]==rid),None)
    if not allowed:
        raise HTTPException(404,"demo_run_not_found")
    detail=_get("/api/runs/"+rid)
    if not _core_detail_matches_listed_run(detail, allowed):
        return {"run_id":rid,"status":"UNKNOWN","source":"Core identity unverified",
                "events":"INCONNU","gates":{"status":"UNKNOWN"}}
    run=detail["run"]
    ledger={"status":"UNKNOWN","reason":"viewer_authorization_required"}
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

@app.get("/qualification-lab",response_class=HTMLResponse)
def qualification_lab(mode:str="simple",seed:int=20261021):
    """Read-only simulation preview: no model evaluation or privileged actions."""
    from portal.qualification_lab import MODES,preview
    if mode not in MODES or not 0<=seed<=2147483647:
        raise HTTPException(422,"invalid_lab_parameters")
    rows=preview(mode,seed)
    form='<form method="get" action="/qualification-lab"><label>Mode <select name="mode">'
    for option in MODES:
        form+='<option value="'+esc(option)+'"'+(' selected' if option==mode else '')+'>'+esc(option)+'</option>'
    form+='</select></label> <label>Graine <input type="number" min="0" max="2147483647" name="seed" value="'+str(seed)+'"></label> <button type="submit">Prévisualiser</button></form>'
    body=panel("Pilotage des scénarios ACME — lecture seule",form+
         '<p><strong>'+str(len(rows))+' observations de démonstration.</strong> Aucune inférence DGX, aucun score IA, aucun événement Evidence, aucune action HITL ou GLPI.</p>')
    rendered=''.join('<tr><td>'+esc(e["timestamp"])+'</td><td>'+esc(e["ci_id"])+
        '</td><td>'+esc(e["kind"])+'</td><td>'+esc(e["description"])+'</td></tr>' for e in rows)
    body+=panel("Observations simulées",'<table><thead><tr><th>Horodatage</th><th>CI ACME</th><th>Type</th><th>Description</th></tr></thead><tbody>'+rendered+'</tbody></table>')
    body+=panel("Qualification des raisonnements",
         '<p>Le banc burn-in et ses KPI ne seront affichés ici qu’après exécution de vraies prédictions Analyst/Critic. Aucun score synthétique n’est présenté comme un résultat de modèle.</p>')
    return shell("/qualification","Laboratoire ACME","Scénarios simples, complexes, chaos et smoke screen — prévisualisation sécurisée.",body)


@app.get("/acme-stories",response_class=HTMLResponse)
def acme_stories_page():
    """Client narrative catalog; links only to previously verified running features."""
    from portal.acme_stories import STORIES
    maturity={
        "TABLETOP_ONLY":"Simulation narrative uniquement",
        "HISTORICAL_DGX":"Parcours DGX historique disponible",
        "BENCHMARK_ONLY":"Générateur / qualification hors ligne",
    }
    body='<p>Choisir une histoire pour expliquer le problème métier, les preuves, les décisions IA et le contrôle humain. Aucun incident ni ticket n’est créé par cette page.</p>'
    for story in STORIES:
        lines=[
            ("Demandeur",story["persona"]),("Impact métier",story["business_impact"]),
            ("Service",story["service"]),("Signal initial",story["symptom"]),
            ("Hypothèse à confirmer",story["hypothesis"]),
            ("Contrôle humain",story["control"]),("Résultat à présenter",story["outcome"]),
            ("Maturité",maturity[story["status"]]),
        ]
        body+=panel(story["title"],table(["Rubrique","Scénario ACME"],lines))
    body+=panel("Démonstrations vérifiables",
        '<p><a href="/demo-studio/run/RUN-A4449145A6E377FF">Analyse DGX historique et Critic</a> · '
        '<a href="/qualification-lab">Laboratoire de scénarios</a> · '
        '<a href="/copilot">Copilot ACME</a></p>')
    return shell("/demo-studio","Histoires métier ACME",
                 "Parcours clients, sécurité, limites et preuves réellement disponibles.",body)


@app.get("/policy-control",response_class=HTMLResponse)
def policy_control_center():
    """Read-only control center; changes are deliberately not available here."""
    url=os.getenv("POLICY_URL","http://aiops2-policy:813")
    state=_get("/api/policy/autonomy",url)
    history=_get("/api/policy/autonomy/history",url)
    simulation=_get("/api/policy/simulation/summary",url)
    decisions=_get("/api/policy/simulation/decisions",url)
    status=state.get("mode","UNKNOWN")
    entries=history.get("items",[]) if isinstance(history.get("items"),list) else []
    rows=[(str(e.get("revision","?")),str(e.get("mode","?")),
           str(e.get("actor","?")),str(e.get("reason","?")),str(e.get("changed_at","?")))
          for e in entries if isinstance(e,dict)]
    body=panel("Mode opérationnel actuel",
        '<p><strong>'+esc(status)+'</strong> — '+esc(state.get("source","source indisponible"))+'</p>'+
        '<p>Affichage en lecture seule. Aucun bouton de réactivation n’est disponible. '
        'Une autorisation indépendante et un contrôle au point d’exécution sont nécessaires avant toute remédiation.</p>')
    body+=panel("Historique audité",table(["Révision","Mode","Acteur","Motif","Date"],rows)
          if rows else '<p>Aucun historique accessible. L’état réel ne doit pas être supposé.</p>')
    if simulation.get("healthy") is True:
        body+=panel("KPI de simulation",
            table(["Mesure","Valeur"],[
              ("Réservations simulées",str(simulation.get("reservations_recorded","INCONNU"))),
              ("Refus enregistrés",str(simulation.get("refusals_recorded","INCONNU"))),
              ("Effets LIVE qualifiés","NON"),
            ]))
    else:
        body+=panel("KPI indisponibles",'<p>Source Policy indisponible ou qualification non déployée. Aucun chiffre supposé.</p>')
    audit=decisions.get("items",[]) if isinstance(decisions.get("items"),list) else []
    if audit:
        body+=panel("Décisions de simulation récentes",table(
            ["Opération","Révision","Classe","Décision","Horodatage"],[
              (str(e.get("operation_id","?")),str(e.get("revision","?")),
               str(e.get("operation_class","?")),str(e.get("reason","?")),
               str(e.get("recorded_at","?"))) for e in audit if isinstance(e,dict)]))
    body+=panel("Maturité et limites",
        '<p>Le registre et les API nécessitent déploiement et qualification. '
        'Le mode STOP_AUTO par défaut n’équivaut pas à une interposition déjà déployée chez les exécuteurs.</p>')
    return shell("/policy-control","Policy Control Center",
                 "Contrôle d’autonomie AIOps — état et historique, lecture seule.",body)

@app.get("/policy-story",response_class=HTMLResponse)
def policy_story():
    """Static, browser-driven demo: no server writes and no operational policy control."""
    script = """
(function(){
 const events=[
  ["Claire — Paie","Je ne peux pas accéder à PAYROLL-X. La clôture des salaires est prioritaire."],
  ["AIOps","Incident qualifié. Je recherche les dépendances et les signaux techniques."],
  ["Observabilité ACME","HTTP 503, 0/2 backends sains sur le load balancer simulé."],
  ["Analyst — simulation","Hypothèse : pool de backends indisponible. Un redémarrage pourrait être envisagé après diagnostic."],
  ["Policy — simulation","Freeze de fin de mois : modification non autorisée sans dérogation management et Change."],
  ["Management — simulation","Documentez le risque, l’impact et le plan de retour arrière avant toute décision."],
  ["AIOps — simulation","Je prépare la demande de changement ; aucune action réelle n’est déclenchée."],
  ["Policy STOP_AUTO — simulation","Arrêt des remédiations autonomes activé dans cette histoire uniquement."],
  ["Contrôle final — simulation","Ancienne réservation devenue invalide. Exécution refusée."],
  ["Synthèse","Incident ouvert, approbation en attente, zéro redémarrage, aucune résolution revendiquée."]
 ];
 let pos=-1;
 const output=document.getElementById("story-events");
 const status=document.getElementById("story-progress");
 function paint(){
  output.replaceChildren();
  for(let i=0;i<=pos;i++){
   const box=document.createElement("section");box.className="card";
   const strong=document.createElement("strong");strong.textContent=events[i][0];
   const paragraph=document.createElement("p");paragraph.textContent=events[i][1];
   box.append(strong,paragraph);output.appendChild(box);
  }
  status.textContent="Étape "+(pos+1)+" / "+events.length+" — simulation locale, aucune API d'écriture";
  document.getElementById("story-next").disabled=pos===events.length-1;
 }
 document.getElementById("story-next").addEventListener("click",()=>{if(pos<events.length-1){pos++;paint();}});
 document.getElementById("story-reset").addEventListener("click",()=>{pos=-1;paint();});
 paint();
})();
"""
    body=panel("Simulation interactive : incident Paie",
       '<p><strong>FICTIF / SANS EFFET</strong> — ce parcours raconte une enquête AIOps et '
       'illustre le blocage des remédiations automatiques pendant un freeze. '
       'Ce n’est pas une réponse DGX en temps réel, un changement Policy réel ou une approbation management.</p>'
       '<p><button id="story-next" type="button">Étape suivante</button> '
       '<button id="story-reset" type="button">Recommencer</button></p>'
       '<p id="story-progress" role="status" aria-live="polite"></p>'
       '<div id="story-events"></div><script>'+script+'</script>')
    body+=panel("Preuves et limites",
        '<p>Données et dialogues simulés. Aucun ticket GLPI, aucune modification de CI, '
        'aucun redémarrage, aucune approbation réelle. '
        'Le contrôle transactionnel STOP_AUTO est testé séparément dans le banc Policy.</p>'
        '<p><a href="/acme-stories">Autres histoires métier</a> · '
        '<a href="/policy-control">Policy Control Center (état réel si disponible)</a></p>')
    return shell("/demo-studio","ACME — Freeze Button Story",
        "Démonstration guidée des interactions humaines et de l'autonomie contrôlée.",body)
