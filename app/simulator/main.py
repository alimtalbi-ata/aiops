import os
from fastapi import FastAPI,Header,HTTPException
from pydantic import BaseModel
from shared.http import post_json,get_json
from shared.ids import new
app=FastAPI(title='ACME Synthetic Scenario & Replay Engine',version='2.0.0')
CORE=os.getenv('CORE_URL','http://aiops2-core:810'); TOKEN=os.getenv('AIOPS_INTERNAL_TOKEN') or os.getenv('AIOPS_ADMIN_TOKEN')
if not TOKEN: raise RuntimeError('AIOPS_INTERNAL_TOKEN or AIOPS_ADMIN_TOKEN must be configured')
class Scenario(BaseModel):name:str;seed:int;scenario_id:str|None=None
class Launch(BaseModel):scenario_id:str='SCN-GOLDEN-PAYMENT-P1';mode:str='DEMO';idempotency_key:str|None=None
class RepresentativeSuite(BaseModel):suite_id:str|None=None;mode:str='DEMO'
@app.get('/health')
def health():return {'status':'ok','component':'simulator','synthetic_only':True,'modes':['DEMO','REPLAY','STORY']}
@app.get('/api/scenarios')
def scenarios():
 # Read-only proxy to the authoritative scenario catalog.
 return get_json(CORE,'/api/dashboard',token=TOKEN)
@app.post('/api/scenarios')
def create(x:Scenario,authorization:str|None=Header(default=None)):
 if (authorization or '').removeprefix('Bearer ')!=TOKEN:raise HTTPException(401,'invalid internal token')
 sid=x.scenario_id or new('SCN'); post_json(CORE,'/api/scenarios/register',{'scenario_id':sid,'name':x.name,'seed':x.seed},token=TOKEN);return {'scenario_id':sid,'name':x.name,'seed':x.seed,'synthetic':True}
@app.post('/api/launch')
def launch(x:Launch,authorization:str|None=Header(default=None)):
 if (authorization or '').removeprefix('Bearer ')!=TOKEN:raise HTTPException(401,'invalid internal token')
 mode=x.mode.upper()
 if mode not in ('DEMO','REPLAY','STORY'):raise HTTPException(422,'simulator cannot launch LIVE')
 key=x.idempotency_key or f'{mode}-{x.scenario_id}-{new("ID")}'
 iid=post_json(CORE,'/api/incidents',{'external_id':key,'title':f'{mode} — {x.scenario_id}','severity':'P1','service_id':'ACME-SVC-PAYMENTS','source':'synthetic-simulator','synthetic':True,'payload':{'scenario_id':x.scenario_id,'mode':mode}},token=TOKEN)['incident_id']
 run=post_json(CORE,'/api/runs',{'mode':mode,'scenario_id':x.scenario_id,'incident_id':iid,'idempotency_key':key},token=TOKEN)
 return post_json(CORE,f"/api/runs/{run['run_id']}/execute",{},token=TOKEN)
@app.post('/api/demo/golden')
def golden(authorization:str|None=Header(default=None)):
 if (authorization or '').removeprefix('Bearer ')!=TOKEN:raise HTTPException(401,'invalid internal token')
 return launch(Launch(),authorization)


_REPRESENTATIVE_CASES = [
    {
        "scenario_id": "SCN-ACME-TEST-RESOLVE-PAYMENTS",
        "name": "TEST — Paiements dégradés avec métriques concordantes",
        "seed": 301,
        "expected_outcome": "RESOLVED",
        "description": (
            "Incident synthétique de latence Payments. Les observations p95 et taux "
            "d'erreur sont dégradées par rapport à leur baseline. Les preuves sont "
            "concordantes et l'objectif métier est un diagnostic complet puis une "
            "résolution DEMO si Analyst, Critic et Policy valident les préconditions."
        ),
    },
    {
        "scenario_id": "SCN-ACME-TEST-RESOLVE-SAN",
        "name": "TEST — Chemin SAN dégradé avec fabric redondante saine",
        "seed": 302,
        "expected_outcome": "RESOLVED",
        "description": (
            "Incident synthétique SAN : erreurs FC élevées sur Fabric A, Fabric B "
            "annoncée saine et multipathing partiellement dégradé. Distinguer les "
            "faits des hypothèses et vérifier le rétablissement en DEMO."
        ),
    },
    {
        "scenario_id": "SCN-ACME-TEST-HITL-CHANGE",
        "name": "TEST — Paiements pendant une fenêtre de changement",
        "seed": 303,
        "expected_outcome": "HITL",
        "description": (
            "Incident synthétique pendant une fenêtre de changement non confirmée. "
            "Aucune action modifiant l'état ne doit être exécutée. Si l'analyse et "
            "le Critic valident une action advisory_only nécessitant une approbation, "
            "créer une proposition HITL et laisser le Run BLOCKED."
        ),
    },
    {
        "scenario_id": "SCN-ACME-TEST-HITL-STORAGE",
        "name": "TEST — Multipathing stockage nécessitant validation humaine",
        "seed": 304,
        "expected_outcome": "HITL",
        "description": (
            "Incident synthétique de chemins stockage dégradés. La collecte de "
            "diagnostics complémentaires doit rester read-only et être proposée "
            "en HITL après validation Analyst/Critic."
        ),
    },
    {
        "scenario_id": "SCN-ACME-TEST-HITL-CRITICAL",
        "name": "TEST — Incident Payments critique à impact élevé",
        "seed": 305,
        "expected_outcome": "HITL",
        "description": (
            "Incident synthétique critique avec impact métier élevé. Exiger une "
            "proposition HITL explicite, documenter le risque et les préconditions. "
            "Ne jamais exécuter de remédiation dans ce scénario de test."
        ),
    },
    {
        "scenario_id": "SCN-ACME-TEST-BLOCK-EVIDENCE",
        "name": "TEST — Preuves contradictoires ou insuffisantes",
        "seed": 306,
        "expected_outcome": "BLOCKED",
        "description": (
            "Incident synthétique avec preuves incomplètes ou contradictoires. "
            "Le Critic doit signaler les lacunes et empêcher toute résolution "
            "affirmée. Le résultat attendu est un Run BLOCKED sans proposition "
            "de remédiation non étayée."
        ),
    },
]


@app.post('/api/demo/representative-suite')
def launch_representative_suite(x: RepresentativeSuite,
                                authorization: str | None = Header(default=None)):
    """Register and launch six reproducible DEMO incidents for GLPI end-to-end tests."""
    if (authorization or '').removeprefix('Bearer ') != TOKEN:
        raise HTTPException(401, 'invalid internal token')
    mode = x.mode.upper()
    if mode != 'DEMO':
        raise HTTPException(422, 'representative_suite_is_demo_only')
    suite_id = (x.suite_id or new('SUITE')).strip()
    if not suite_id or len(suite_id) > 80 or any(ch.isspace() for ch in suite_id):
        raise HTTPException(422, 'invalid_suite_id')
    launched = []
    for case in _REPRESENTATIVE_CASES:
        post_json(CORE, '/api/scenarios/register', {
            'scenario_id': case['scenario_id'],
            'name': case['name'],
            'seed': case['seed'],
            'description': case['description'],
        }, token=TOKEN)
        result = launch(Launch(
            scenario_id=case['scenario_id'],
            mode='DEMO',
            idempotency_key=f"DEMO-ENRICHED-{suite_id}-{case['scenario_id']}",
        ), authorization)
        launched.append({
            'scenario_id': case['scenario_id'],
            'name': case['name'],
            'expected_outcome': case['expected_outcome'],
            'run_id': result.get('run_id'),
            'workflow_id': result.get('workflow_id'),
            'launch_result': result,
        })
    return {
        'suite_id': suite_id,
        'mode': 'DEMO',
        'count': len(launched),
        'items': launched,
        'note': (
            'expected_outcome is a test target, not a forced result. '
            'Actual Run and GLPI ticket outcomes must be verified after workflow completion.'
        ),
        'execution_allowed': False,
    }
