"""Render static, interactive NOC wallboard from validated synthetic snapshot."""
from __future__ import annotations
import argparse
import html
import json
from pathlib import Path
from demo.noc_synthetic_snapshot import build_noc_snapshot
from demo.validate_rag_ops_fixtures import validate_catalog
from demo.noc_topology import build_noc_topology
from demo.noc_drilldown import build_noc_drilldown

def render_noc_wallboard(snapshot: dict, catalog: dict | None = None) -> str:
    if not isinstance(snapshot,dict) or snapshot.get("schema")!="aiops-noc-synthetic-snapshot-v1" or snapshot.get("provenance")!="SYNTHETIC_SIMULATION_ONLY":
        raise ValueError("unsupported NOC snapshot")
    if any(snapshot.get(k) is not False for k in ("runtime_authenticated","checkmk_live","thruk_live","live_remediation_authorized")):
        raise ValueError("forged NOC live attestation")
    hosts, services, alerts=snapshot.get("hosts"),snapshot.get("business_services"),snapshot.get("alerts")
    if not isinstance(hosts,dict) or not isinstance(services,dict) or not isinstance(alerts,list):
        raise ValueError("invalid NOC data")
    if len(hosts)>100 or len(services)>30 or len(alerts)>500:
        raise ValueError("oversized NOC dataset")
    esc=lambda v: html.escape(str(v),quote=True)
    def row(name,state,detail):
        if state not in ("OK","WARN","CRIT","UNKNOWN"):
            raise ValueError("invalid NOC severity")
        return f'<tr data-state="{state}"><td>{esc(name)}</td><td><span class="state {state}">{state}</span></td><td>{esc(detail)}</td></tr>'
    hostrows="".join(row(k,v["state"],str(v["alerts"])+" alert(s)") for k,v in sorted(hosts.items()))
    servicerows="".join(row(k,v["state"],str(v["alerts"])+" alert(s)") for k,v in sorted(services.items()))
    eventrows="".join(row(v["asset_id"],v["state"],v["event_id"]+" · "+v["signal"]) for v in alerts)
    topology=build_noc_topology(snapshot)
    node_by_id={n["id"]:n for n in topology["nodes"]}
    dependency_rows="".join(row(edge["from"]+" → "+edge["to"],node_by_id[edge["from"]]["state"],node_by_id[edge["from"]]["role"]) for edge in topology["edges"])
    detail_panels=""
    if catalog is not None:
        drill=build_noc_drilldown(snapshot,catalog)
        for name,asset in sorted(drill["assets"].items()):
            sources="".join("<li><strong>"+esc(d["doc_id"])+"</strong> — "+esc(d["sample"])+"<ol>"+"".join("<li>"+esc(a)+"</li>" for a in d["runbook"])+"</ol></li>" for d in asset["diagnostics"])
            detail_panels+="<details><summary>"+esc(name)+" — "+esc(asset["state"])+"</summary><p>Amont : "+esc(", ".join(asset["upstream"]) or "aucun")+" · Aval : "+esc(", ".join(asset["downstream"]) or "aucun")+"</p><ul>"+sources+"</ul></details>"
    return """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIOps NOC — Simulation</title>
<style>
:root{color-scheme:dark;font:15px system-ui;background:#081423;color:#edf5ff}
body{margin:0;padding:20px;max-width:1700px}
header,.grid,.stats{display:grid;gap:14px}.stats{grid-template-columns:repeat(3,minmax(120px,1fr))}
.grid{grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
section,.metric{background:#10273d;border:1px solid #254866;border-radius:12px;padding:16px}details{margin:8px 0;padding:10px;border:1px solid #254866;border-radius:6px}summary{cursor:pointer}
h1{margin:0 0 8px;font-size:24px}h2{margin-top:0;font-size:17px}
.metric strong{font-size:32px;display:block}small{color:#a8c7db}
table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:10px 6px;border-bottom:1px solid #284259}
.state{font-weight:bold;padding:4px 8px;border-radius:5px}.CRIT{background:#6d202e;color:#ffd6db}
.WARN{background:#64470d;color:#ffe5a0}.OK{background:#104838;color:#acffd9}.UNKNOWN{background:#30415a}
button{padding:8px 12px;background:#244866;color:white;border:1px solid #477ba8;border-radius:6px;cursor:pointer}
button[aria-pressed=true]{outline:2px solid #8bc6ff}footer{margin-top:20px;color:#a8c7db}
</style></head><body>
<header><h1>AIOps — NOC Command Center</h1>
<p>DONNÉES SYNTHÉTIQUES DE DÉMONSTRATION · Pas de connexion Checkmk/Thruk en direct</p></header>
<div class="stats">
<div class="metric"><small>Hôtes</small><strong>""" + esc(len(hosts)) + """</strong></div>
<div class="metric"><small>Services métiers</small><strong>""" + esc(len(services)) + """</strong></div>
<div class="metric"><small>Alertes simulées</small><strong>""" + esc(len(alerts)) + """</strong></div>
</div><p>Run : <code>""" + esc(snapshot.get("run_id","")) + """</code></p>
<nav aria-label="Filtrer les états"><button data-filter="ALL" aria-pressed="true">Tous</button>
<button data-filter="CRIT" aria-pressed="false">Critiques</button>
<button data-filter="WARN" aria-pressed="false">Avertissements</button>
<button data-filter="OK" aria-pressed="false">OK</button></nav>
<section><h2>Topologie d’impact SAN → Stockage → Calcul → ACME Payments</h2><small>Relations CMDB SYNTHÉTIQUES — non découvertes dans Checkmk/Thruk</small><table><thead><tr><th>Dépendance</th><th>État source</th><th>Rôle</th></tr></thead><tbody>""" + dependency_rows + """</tbody></table></section><section><h2>Diagnostic par équipement et procédures RAG</h2><small>Runbooks SYNTHÉTIQUES, aucune commande LIVE</small>""" + detail_panels + """</section><div class="grid"><section><h2>Équipements</h2><table><thead><tr><th>Hôte</th><th>État</th><th>Détail</th></tr></thead><tbody>""" + hostrows + """</tbody></table></section>
<section><h2>Impact métier</h2><table><thead><tr><th>Service</th><th>État</th><th>Détail</th></tr></thead><tbody>""" + servicerows + """</tbody></table></section>
<section><h2>Alertes et signaux</h2><table><thead><tr><th>CI</th><th>État</th><th>Événement / signal</th></tr></thead><tbody>""" + eventrows + """</tbody></table></section></div>
<footer>Mode simulation · Aucune action d'acquittement, aucun redémarrage et aucune remédiation LIVE.</footer>
<script>
document.querySelectorAll('button[data-filter]').forEach(b=>b.addEventListener('click',()=>{
const f=b.dataset.filter;
document.querySelectorAll('button[data-filter]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
document.querySelectorAll('tbody tr').forEach(row=>{row.hidden=f!=='ALL'&&row.dataset.state!==f});
}));
</script></body></html>"""

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--catalog",type=Path,default=Path(__file__).with_name("rag_ops_fixture_catalog.json"))
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    catalog=json.loads(a.catalog.read_text(encoding="utf8"))
    validate_catalog(catalog)
    page=render_noc_wallboard(build_noc_snapshot(catalog),catalog)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open("x",encoding="utf8") as stream: stream.write(page)
    print("NOC_SYNTHETIC_WALLBOARD_CREATED")
if __name__=="__main__":main()
