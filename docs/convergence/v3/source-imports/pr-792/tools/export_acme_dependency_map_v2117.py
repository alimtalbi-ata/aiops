#!/usr/bin/env python3
"""Offline ACME dependency explorer, all topology and impacts are SYNTHETIC."""
import argparse,hashlib,html,importlib.util,json
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
def get_catalog():
    spec=importlib.util.spec_from_file_location("acme_offline_v2116",BASE/"tools/export_acme_offline_demo_v2116.py")
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m.load_stories()
# Explicit fictitious topology; not CMDB data, nor inferred real root causes.
EDGES={
 "PAYROLL_FREEZE":[("PAYROLL-X","ACME-LB-PAYROLL"),("ACME-LB-PAYROLL","ACME-APP-PAYROLL01"),("ACME-APP-PAYROLL01","ACME-DB-PAYROLL")],
 "PAYMENTS_SAN":[("Payment Processing","ACME-SRV-RHEL01"),("ACME-SRV-RHEL01","ACME-SAN-FABRIC-A"),("ACME-SAN-FABRIC-A","ACME-STO-PURE01")],
 "ERP_DATABASE":[("Oracle ERP","ACME-APP-ERP01"),("ACME-APP-ERP01","ACME-DB-ORACLE01"),("ACME-DB-ORACLE01","ACME-STO-PURE01")],
 "IDENTITY_OUTAGE":[("Identity & Access","ACME-IDP01"),("ACME-IDP01","ACME-AD01")],
 "RANSOMWARE_SIGNAL":[("NAS Production","ACME-NAS01"),("ACME-NAS01","ACME-SHARE01")],
 "MULTI_ROOT_CHAOS":[("Payments + ERP","ACME-SRV-RHEL01"),("ACME-SRV-RHEL01","ACME-SAN-FABRIC-A"),("Payments + ERP","ACME-APP-ERP01"),("ACME-APP-ERP01","ACME-NET-CORE-A")]
}
def build(stories):
    ids={s["id"] for s in stories}
    if ids!=set(EDGES):raise ValueError("topology/catalog mismatch")
    entries=[]
    for s in stories:
        edges=EDGES[s["id"]]
        if len(edges)!=len(set(edges)) or any(a==b for a,b in edges):raise ValueError("invalid edges")
        nodes=list(dict.fromkeys(node for edge in edges for node in edge))
        if s["service"] not in nodes:raise ValueError("business service absent")
        entries.append({"id":s["id"],"title":s["title"],"service":s["service"],"impact":s["business_impact"],"symptom":s["symptom"],"hypothesis":s["hypothesis"],"control":s["control"],"status":s["status"],"nodes":nodes,"edges":edges})
    payload=json.dumps(entries,ensure_ascii=False).replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
    return """<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ACME — Carte des dépendances (simulation)</title><style>
:root{color-scheme:dark;font-family:system-ui;background:#081522;color:#edf6ff}body{max-width:1180px;margin:auto;padding:24px}
h1{font-size:clamp(2rem,4vw,3.2rem)}p{color:#c0d3e3;line-height:1.5}.banner{background:#513d19;padding:15px;border-radius:10px}
select,button{padding:12px;border-radius:8px;background:#193650;color:#fff;border:1px solid #749bb8;font:inherit}
main{display:grid;grid-template-columns:2fr 1fr;gap:20px;margin-top:20px}.panel{background:#122b43;border-radius:12px;padding:18px}
.graph{display:flex;flex-wrap:wrap;align-items:center;gap:9px;min-height:240px}.node{border:1px solid #5abfc8;border-radius:10px;padding:14px;background:#173c50;cursor:pointer}
.node[aria-pressed=true]{background:#7c430c;color:white;border-color:#ffcd69}.arrow{color:#ffc66c;font-size:1.4rem}
dt{margin-top:15px;color:#8ee0d6}dd{margin:3px 0 10px}footer{margin-top:22px;color:#b5cbdc}
@media(max-width:780px){main{grid-template-columns:1fr}}
</style><body><header><p>ACME DIGITAL TWIN · HORS LIGNE</p><h1>Cartographie des impacts et dépendances</h1><p class="banner"><strong>TOPOLOGIE 100 % SYNTHÉTIQUE.</strong> Aucun accès CMDB, aucune télémétrie LIVE, aucune analyse DGX ici. Les liens sont fictifs, illustratifs et ne prouvent aucune causalité.</p>
<label for="scenario">Incident métier :</label> <select id="scenario"></select>
</header><main><section class="panel"><h2 id="title"></h2><p id="impact"></p><div class="graph" id="graph" aria-label="Dépendances illustratives"></div><p>Cliquez un composant pour afficher son rôle dans cette chaîne fictive.</p></section>
<aside class="panel"><h2>Analyse contextualisée</h2><dl><dt>Composant sélectionné</dt><dd id="selected">Aucun</dd><dt>Symptôme</dt><dd id="symptom"></dd><dt>Hypothèse non validée</dt><dd id="hypothesis"></dd><dt>Contrôle recommandé</dt><dd id="control"></dd><dt>Nature des données</dt><dd id="provenance"></dd></dl><p><strong>Décision :</strong> aucune remédiation et aucune approbation exécutées.</p></aside></main>
<footer>Modèle illustratif ACME. Une cartographie réelle requiert CMDB, découvertes et preuves corrélées. Run DGX historique distinct : RUN-A4449145A6E377FF.</footer>
<script id="acme-data" type="application/json">"""+payload+"""</script><script>
(function(){
"use strict";
const data=JSON.parse(document.getElementById("acme-data").textContent);
const scenario=document.getElementById("scenario");
for(const record of data){const option=document.createElement("option");option.value=record.id;option.textContent=record.title;scenario.append(option);}
function put(id,value){document.getElementById(id).textContent=value;}
function show(){
 const s=data.find(item=>item.id===scenario.value);if(!s)return;
 put("title",s.title);put("impact",s.impact);put("symptom",s.symptom);
 put("hypothesis",s.hypothesis);put("control",s.control);
 put("provenance",s.status==="HISTORICAL_DGX"?"Topologie synthétique ; un run DGX historique distinct existe":s.status==="BENCHMARK_ONLY"?"Benchmark synthétique non validé par DGX":"Scénario fictif non exécuté");
 put("selected","Aucun");const graph=document.getElementById("graph");graph.replaceChildren();
 for(let i=0;i<s.nodes.length;i++){
  const button=document.createElement("button");button.className="node";button.type="button";button.textContent=s.nodes[i];button.setAttribute("aria-pressed","false");
  button.addEventListener("click",()=>{for(const n of graph.querySelectorAll(".node"))n.setAttribute("aria-pressed","false");button.setAttribute("aria-pressed","true");put("selected",s.nodes[i]+" — CI fictif (aucun état réel connu)");});
  graph.append(button);if(i<s.nodes.length-1){const sep=document.createElement("span");sep.className="arrow";sep.textContent="→";sep.setAttribute("aria-hidden","true");graph.append(sep);}
 }
}
scenario.addEventListener("change",show);show();
})();
</script></body></html>"""
def export(output):
    output.mkdir(parents=True,exist_ok=True)
    page=output/"ACME-DEPENDENCY-MAP.html"
    page.write_text(build(get_catalog()),encoding="utf-8")
    manifest={"version":"2.11.7","source":"ACME synthetic catalog and explicit illustrative dependencies","mode":"OFFLINE_SYNTHETIC","effects":"NONE","sha256":hashlib.sha256(page.read_bytes()).hexdigest()}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return manifest
if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,default=Path("/tmp/acme-offline-v2117"));args=parser.parse_args();print(json.dumps(export(args.output),indent=2,ensure_ascii=False))
