#!/usr/bin/env python3
"""V2.11.9: unified ACME offline storytelling; synthetic, no operational effect."""
import argparse,hashlib,html,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def module(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/"tools"/file)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def dataset():
    dep=module("acme_dep_2119","export_acme_dependency_map_v2117.py")
    investigation=module("acme_invest_2119","export_acme_investigation_cockpit_v2118.py")
    stories={s["id"]:s for s in dep.get_catalog()}
    events={row["id"]:row for row in investigation.records()}
    if set(stories)!=set(dep.EDGES) or set(events)!=set(stories):raise ValueError("catalog mismatch")
    output=[]
    for id,story in stories.items():
        edges=dep.EDGES[id];timeline=events[id]["timeline"]
        nodes=list(dict.fromkeys(v for edge in edges for v in edge))
        if story["service"] not in nodes or len(timeline)!=7 or any(e["ci"] not in nodes or e["source"]!="SYNTHETIC" for e in timeline):raise ValueError("invalid graph/evidence")
        output.append({"id":id,"title":story["title"],"impact":story["business_impact"],"symptom":story["symptom"],
         "hypothesis":story["hypothesis"],"control":story["control"],"status":story["status"],"nodes":nodes,
         "edges":edges,"timeline":timeline,"policy":"DENY_SIMULATION_ONLY","execution_allowed":False})
    return output
def build(records):
    if len(records)!=6 or len({r["id"] for r in records})!=6 or any(r["execution_allowed"] is not False for r in records):raise ValueError("unsafe stories")
    data=json.dumps(records,ensure_ascii=False).replace("<",r"\u003c").replace(">",r"\u003e").replace("&",r"\u0026")
    return """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ACME | Mission Control hors ligne</title>
<style>:root{color-scheme:dark;font:16px system-ui,Segoe UI,sans-serif;background:#071426;color:#eff7ff}body{max-width:1300px;margin:auto;padding:24px}header{background:radial-gradient(ellipse at top right,#21597c,transparent 72%),#10243e;padding:25px;border-radius:18px}h1{font-size:clamp(2rem,5vw,3.7rem);margin:10px 0}.notice{padding:13px;background:#5b3a16;border-left:4px solid #ffd278;border-radius:8px}p{line-height:1.5;color:#c2d5e5}select,button{background:#1c4562;color:#fff;border:1px solid #639eb6;padding:12px;border-radius:8px;font:inherit}button{cursor:pointer}button:focus-visible,select:focus-visible{outline:3px solid #ffc66e}.cards{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:20px 0}.card{background:#112d48;border:1px solid #34556b;border-radius:14px;padding:20px}.nodes{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.node{background:#193f54}.node[aria-pressed=true],.event[aria-pressed=true]{background:#865017;border-color:#ffd278}.event{display:block;width:100%;margin:8px 0;text-align:left}.meta{display:block;color:#a5ecdc;font-size:.85rem}.state{color:#ffc66e;font-weight:bold}.actions{display:flex;gap:10px;flex-wrap:wrap}dt{color:#a0e8dc;margin-top:12px}dd{margin:3px 0}footer{padding:15px}@media(max-width:800px){.cards{grid-template-columns:1fr}}
</style></head><body><header><p>ACME DIGITAL TWIN — MISSION CONTROL</p><h1>De l'impact métier à la décision contrôlée</h1><p class="notice"><strong>SIMULATION SYNTHÉTIQUE HORS LIGNE.</strong> Aucun accès CMDB, DGX, métriques réelles ou approbation humaine. Analyst/Critic ci-dessous sont fictifs. Aucune remédiation LIVE. Référence historique distincte : RUN-A4449145A6E377FF.</p><label for="scenario">Incident métier : </label><select id="scenario"></select></header>
<main class="cards"><section class="card"><h2>Impact et dépendances</h2><h3 id="name"></h3><p id="impact"></p><div id="nodes" class="nodes"></div><p id="node-detail">Sélectionner un CI fictif.</p></section>
<section class="card"><h2>Analyse et décision</h2><dl><dt>Symptôme illustratif</dt><dd id="symptom"></dd><dt>Hypothèse Analyst (simulée)</dt><dd id="hypothesis"></dd><dt>Contrôle/objection Critic (simulé)</dt><dd id="critic">Causalité à corroborer par des preuves réelles.</dd><dt>Policy Manager (simulation)</dt><dd id="control"></dd><dt>Résultat</dt><dd class="state">REFUS SIMULÉ — zéro commande, approbation en attente</dd><dt>Provenance</dt><dd id="origin"></dd></dl></section>
<section class="card"><h2>Chronologie d'investigation</h2><p id="count"></p><div id="events"></div><div class="actions"><button id="reset" type="button">Recommencer</button></div></section>
<section class="card"><h2>Preuves et limitations</h2><p id="focus">Sélectionnez un événement.</p><p id="ci"></p><p class="notice">Les événements affichés sont générés à partir du catalogue ACME et ne représentent ni une enquête DGX exécutée ni des changements approuvés. Les liens topologiques sont fictifs.</p><p>Pour des preuves d'exécution IA, consulter séparément la timeline historique RUN-A4449145A6E377FF sur le portail opérationnel.</p></section></main>
<footer>Démonstration 100 % autonome. Aucun réseau ni code d'exécution de remédiation.</footer>
<script type="application/json" id="acme-json">"""+data+"""</script><script>
(()=>{"use strict";
 const records=JSON.parse(document.getElementById("acme-json").textContent);
 const select=document.getElementById("scenario");let chosen=0;
 const put=(id,val)=>document.getElementById(id).textContent=val;
 for(const r of records){const o=document.createElement("option");o.value=r.id;o.textContent=r.title;select.append(o);}
 function render(){
 const r=records.find(e=>e.id===select.value);if(!r)return;
 put("name",r.title);put("impact",r.impact);put("symptom",r.symptom);put("hypothesis",r.hypothesis);put("control",r.control);
 put("origin",r.status==="HISTORICAL_DGX"?"Scénario synthétique ; run DGX historique distinct":"Scénario synthétique uniquement");
 const nodes=document.getElementById("nodes");nodes.replaceChildren();
 for(const n of r.nodes){const btn=document.createElement("button");btn.type="button";btn.className="node";btn.textContent=n;btn.setAttribute("aria-pressed","false");btn.onclick=()=>{for(const other of nodes.querySelectorAll("button"))other.setAttribute("aria-pressed","false");btn.setAttribute("aria-pressed","true");put("node-detail",n+" — CI fictif, état réel inconnu");};nodes.append(btn);}
 put("count",r.timeline.length+" événements synthétiques");
 const holder=document.getElementById("events");holder.replaceChildren();
 r.timeline.forEach((e,i)=>{const btn=document.createElement("button");btn.type="button";btn.className="event";btn.setAttribute("aria-pressed",String(chosen===i));const meta=document.createElement("span");meta.className="meta";meta.textContent=e.time+" · "+e.actor+" · "+e.source;const label=document.createElement("span");label.textContent=e.detail;btn.append(meta,label);btn.onclick=()=>{chosen=i;render();};holder.append(btn);});
 put("focus",r.timeline[chosen].detail);put("ci",r.timeline[chosen].ci+" · source : SYNTHETIC");
 }
 select.addEventListener("change",()=>{chosen=0;render();});
 document.getElementById("reset").addEventListener("click",()=>{chosen=0;render();});
 render();
})();
</script></body></html>"""
def export(folder):
    folder.mkdir(parents=True,exist_ok=True)
    page=folder/"ACME-MISSION-CONTROL.html";page.write_text(build(dataset()),encoding="utf-8")
    report={"version":"2.11.9","mode":"OFFLINE_SYNTHETIC","execution_allowed":False,"scenario_count":6,"events_per_scenario":7,"sha256":hashlib.sha256(page.read_bytes()).hexdigest()}
    (folder/"manifest.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report
if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,default=Path("/tmp/acme-mission-control-v2119"))
    args=parser.parse_args();print(json.dumps(export(args.output),indent=2,ensure_ascii=False))
