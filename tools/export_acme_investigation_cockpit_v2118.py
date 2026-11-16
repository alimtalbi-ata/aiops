#!/usr/bin/env python3
"""Read-only, offline ACME investigation timeline. All evidence is synthetic."""
import argparse,hashlib,html,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def source_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
def records():
    topo=source_module("acme_topology_v2117",ROOT/"tools/export_acme_dependency_map_v2117.py")
    catalog=topo.get_catalog()
    events=[]
    for story in catalog:
        graph=topo.EDGES[story["id"]]
        nodes=list(dict.fromkeys(v for pair in graph for v in pair))
        stages=[
          ("00:00","Métier","Incident signalé : "+story["business_impact"],story["service"]),
          ("00:02","Observation fictive",story["symptom"],nodes[1]),
          ("00:04","Topologie illustrative","Dépendance à investiguer : "+nodes[1]+" → "+nodes[-1],nodes[-1]),
          ("00:06","Analyst — hypothèse fictive",story["hypothesis"],nodes[-1]),
          ("00:08","Critic — simulation","Causalité non établie. Croiser les métriques, logs et CI.",nodes[1]),
          ("00:10","Policy — simulation",story["control"]+" ; aucune remédiation autorisée dans cette simulation.",story["service"]),
          ("00:12","Décision humaine — attente","Validation indépendante nécessaire avant toute action réelle.",story["service"])
        ]
        events.append({"id":story["id"],"title":story["title"],"service":story["service"],
         "graph_nodes":nodes,"timeline":[{"time":a,"actor":b,"detail":c,"ci":d,"source":"SYNTHETIC"} for a,b,c,d in stages]})
    return events
def build(data):
    if len(data)!=6 or len({d["id"] for d in data})!=6:raise ValueError("six unique incidents required")
    for item in data:
        times=[e["time"] for e in item["timeline"]]
        if len(times)!=7 or times!=sorted(times) or any(e["ci"] not in item["graph_nodes"] for e in item["timeline"]):raise ValueError("invalid timeline references")
    payload=json.dumps(data,ensure_ascii=False).replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
    return """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ACME | Cockpit d'investigation simulé</title>
<style>:root{color-scheme:dark;font-family:system-ui,Segoe UI,sans-serif;background:#091625;color:#f5fbff}body{max-width:1200px;margin:auto;padding:24px}h1{font-size:clamp(2rem,4vw,3.3rem)}p{line-height:1.5;color:#c9d8e8}.notice{background:#493419;border-left:4px solid #ffd072;padding:16px;border-radius:10px}select,button{font:inherit;padding:11px;border-radius:9px;background:#183d57;color:#fff;border:1px solid #6d9eb8}button{cursor:pointer}button:focus-visible{outline:3px solid #ffd072}.layout{display:grid;grid-template-columns:1.6fr 1fr;gap:18px;margin-top:24px}.panel{border:1px solid #33516b;background:#112a43;border-radius:12px;padding:20px}.event{display:block;text-align:left;width:100%;margin:10px 0;background:#173951}.event[aria-pressed=true]{background:#7a4518;border-color:#ffd072}small{display:block;color:#a4e5dc}.metric{font-weight:bold;color:#b2f0e1}dl dt{color:#99e5d8;margin-top:15px}dl dd{margin:4px 0 10px}#focus{word-break:break-word}footer{margin-top:22px;color:#bbcee0}@media(max-width:740px){.layout{grid-template-columns:1fr}}</style></head>
<body><header><p>ACME DIGITAL TWIN • HORS LIGNE</p><h1>Investigation et contrôle de l'autonomie</h1>
<p class="notice"><strong>SIMULATION INTÉGRALE.</strong> Observations, Analyst, Critic, décisions et CI de cette page sont fictifs. Aucun appel DGX/CMDB, aucune approbation réelle et aucune remédiation LIVE. Le run DGX historique RUN-A4449145A6E377FF est distinct de cette démonstration.</p>
<label for="incident">Incident :</label> <select id="incident"></select></header><main class="layout">
<section class="panel"><h2 id="title"></h2><p class="metric" id="counter"></p><div id="events" aria-label="Chronologie synthétique"></div><button id="replay" type="button">Recommencer</button></section>
<aside class="panel"><h2>Contexte de la décision</h2><dl><dt>Étape sélectionnée</dt><dd id="focus">Aucune</dd><dt>Composant fictif concerné</dt><dd id="component">Aucun</dd><dt>Provenance</dt><dd id="origin">SYNTHETIC</dd><dt>Règle d'autonomie</dt><dd>Aucune commande n'est envoyée aux exécuteurs. Approbation humaine non réalisée.</dd></dl>
<p>Analyse contextuelle <strong>non générée par un modèle</strong>. Les causes racines et impacts restent des hypothèses.</p></aside>
</main><footer>Parcours pédagogique hors ligne — les événements ne proviennent d'aucune collecte de production.</footer>
<script id="payload" type="application/json">"""+payload+"""</script><script>
(function(){
"use strict";
const records=JSON.parse(document.getElementById("payload").textContent);
const select=document.getElementById("incident");
let index=0;
function text(id,value){document.getElementById(id).textContent=value;}
for(const r of records){const o=document.createElement("option");o.value=r.id;o.textContent=r.title;select.append(o);}
function paint(){
 const r=records.find(x=>x.id===select.value);if(!r)return;
 text("title",r.title);text("counter",r.timeline.length+" événements illustratifs • aucune action réelle");
 const root=document.getElementById("events");root.replaceChildren();
 r.timeline.forEach((event,i)=>{
   const button=document.createElement("button");button.className="event";button.type="button";
   button.setAttribute("aria-pressed",String(i===index));
   const meta=document.createElement("small");meta.textContent=event.time+" · "+event.actor+" · "+event.source;
   const detail=document.createElement("span");detail.textContent=event.detail;
   button.append(meta,detail);
   button.addEventListener("click",()=>{index=i;paint();});
   root.append(button);
 });
 const event=r.timeline[index];text("focus",event.detail);text("component",event.ci);text("origin",event.source);
}
select.addEventListener("change",()=>{index=0;paint();});
document.getElementById("replay").addEventListener("click",()=>{index=0;paint();});
paint();
})();
</script></body></html>"""
def export(path):
    path.mkdir(parents=True,exist_ok=True)
    page=path/"ACME-INVESTIGATION-COCKPIT.html"
    page.write_text(build(records()),encoding="utf-8")
    report={"version":"2.11.8","mode":"OFFLINE_SYNTHETIC","effects":"NONE","incident_count":6,"events_per_incident":7,"sha256":hashlib.sha256(page.read_bytes()).hexdigest()}
    (path/"manifest.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,default=Path("/tmp/acme-cockpit-v2118"));a=p.parse_args()
    print(json.dumps(export(a.output),indent=2,ensure_ascii=False))
