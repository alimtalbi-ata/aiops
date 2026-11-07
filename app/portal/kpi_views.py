"""Read-only KPI campaign view sourced from Core canonical run and AI ledgers."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from statistics import median
from fastapi.responses import HTMLResponse
from portal.ui_theme import shell, panel, table, esc

TERMINAL = {"RESOLVED", "BLOCKED", "FAILED", "CANCELLED"}
def seconds(start, end):
    try:
        if not start or not end: return None
        a=datetime.fromisoformat(str(start).replace("Z","+00:00"))
        b=datetime.fromisoformat(str(end).replace("Z","+00:00"))
        return max(0.0,(b-a).total_seconds())
    except (ValueError,TypeError): return None

def percentile(values, p):
    if not values: return None
    ordered=sorted(values)
    pos=(len(ordered)-1)*p
    low=int(pos);high=min(low+1,len(ordered)-1)
    return round(ordered[low]+(ordered[high]-ordered[low])*(pos-low),2)

def metrics(runs, details):
    statuses=Counter(str(r.get("status","UNKNOWN")) for r in runs)
    durations=[]
    analyst=[];critic=[]
    for run in runs:
        duration=seconds(run.get("started_at") or run.get("created_at"),run.get("completed_at"))
        if duration is not None:durations.append(duration)
        detail=details.get(str(run.get("run_id")),{})
        stages=detail.get("stages",[]) if isinstance(detail,dict) else []
        for stage in stages if isinstance(stages,list) else []:
            if not isinstance(stage,dict):continue
            name=str(stage.get("stage","")).upper()
            value=seconds(stage.get("started_at"),stage.get("completed_at"))
            if value is None:continue
            if name in ("ANALYZE","ANALYST"):analyst.append(value)
            if name in ("CRITIQUE","CRITIC"):critic.append(value)
    return {"total":len(runs),"statuses":statuses,"terminal":sum(statuses.get(s,0) for s in TERMINAL),
            "median_seconds":round(median(durations),2) if durations else None,
            "p95_seconds":percentile(durations,.95),
            "analyst_median_seconds":round(median(analyst),2) if analyst else None,
            "critic_median_seconds":round(median(critic),2) if critic else None,
            "duration_samples":len(durations),"analyst_samples":len(analyst),"critic_samples":len(critic)}

def fmt(value):
    return "NON MESURÉ" if value is None else str(value)

def register_kpi_views(app, get_core):
    @app.get("/kpi",response_class=HTMLResponse)
    def kpi_page():
        response=get_core("/api/runs")
        if not isinstance(response,dict) or not isinstance(response.get("items"),list):
            return shell("/kpi","KPI AIOps2","Mesures canoniques, lecture seule",
                         panel("Source indisponible","<p>INCONNU — Core /api/runs indisponible. Aucun KPI inventé.</p>"),mode="LECTURE SEULE")
        all_runs=[r for r in response["items"] if isinstance(r,dict)]
        # Core /api/runs is bounded to its 100 most recent runs; do not imply historical completeness.
        campaign=[r for r in all_runs if str(r.get("scenario_id","")).startswith("FS1130-")]
        details={}
        def load(run):
            rid=str(run.get("run_id",""))
            if not rid or len(rid)>128 or not all(c.isalnum() or c in "-_" for c in rid):return rid,{}
            response=get_core("/api/runs/"+rid)
            return rid,response if isinstance(response,dict) and isinstance(response.get("stages"),list) else {}
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures=[pool.submit(load,r) for r in campaign[:50]]
            for f in as_completed(futures):
                try:
                    rid,detail=f.result()
                    details[rid]=detail
                except Exception:
                    pass
        data=metrics(campaign,details)
        missing_details=sum(1 for r in campaign if not details.get(str(r.get("run_id"))))
        status_rows=[(status,data["statuses"].get(status,0)) for status in ("RESOLVED","BLOCKED","FAILED","CANCELLED","RUNNING","CREATED","WAITING")]
        body=panel("Campagne FS1130 — traitements synthétiques",
            "<p>Source : Core /api/runs et /api/runs/{id}. Vue actualisée à chaque chargement. "
            "Périmètre limité aux 100 derniers runs de Core : les résultats peuvent être partiels. "
            "Les blocages Policy justifiés ne sont pas automatiquement des échecs.</p>"+
            table(["Mesure","Valeur"],[
                ("Runs FS1130 visibles",data["total"]),
                ("États terminaux",data["terminal"]),
                ("Résolus",data["statuses"].get("RESOLVED",0)),
                ("Bloqués Policy / workflow",data["statuses"].get("BLOCKED",0)),
                ("Échecs techniques (FAILED)",data["statuses"].get("FAILED",0)),
                ("Détails de run indisponibles",missing_details),
                ("Durée médiane run (s)",fmt(data["median_seconds"])),
                ("Durée P95 run (s)",fmt(data["p95_seconds"])),
                ("Durée médiane étape Analyst (s)",fmt(data["analyst_median_seconds"])),
                ("Durée médiane étape Critic (s)",fmt(data["critic_median_seconds"])),
                ("Échantillons de durée run / Analyst / Critic",f'{data["duration_samples"]} / {data["analyst_samples"]} / {data["critic_samples"]}'),
            ]))
        body+=panel("Résultats par état",table(["État","Nombre"],status_rows))
        body+=panel("Tokens et coût IA",
            "<p><strong>NON MESURÉ</strong> — les réponses du fournisseur LLM ne conservent actuellement "
            "pas les champs de consommation <code>usage</code> dans le registre Core. "
            "Aucun total de tokens ni coût n'est estimé à partir des caractères.</p>")
        body+=panel("Traçabilité et limites",
            "<p>Les durées Analyst/Critic ci-dessus sont les durées des étapes du workflow, "
            "pas nécessairement le temps réseau exact des appels au modèle. "
            "Les incidents FS1130 ont des titres distincts mais utilisent principalement "
            "les mêmes observations SAN simulées. Cette vue n'injecte aucun incident et "
            "n'exécute aucune remédiation.</p>")
        body+=panel("Navigation","<p><a href='/timeline'>Timeline des incidents</a> · "
            "<a href='/qualification'>Qualification</a> · <a href='/prometheus'>Prometheus</a></p>")
        return shell("/kpi","KPI AIOps2","Qualification et performances réelles du pipeline, sans chiffres inventés",body,mode="LECTURE SEULE")
