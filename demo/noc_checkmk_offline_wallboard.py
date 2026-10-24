"""Render unverified offline Checkmk host/service states as a standalone NOC table."""
from __future__ import annotations
import argparse
import html
import json
from pathlib import Path
from demo.noc_checkmk_consolidation import consolidate_checkmk_snapshot

STATES={"OK","WARN","CRIT","UNKNOWN"}

def render_checkmk_offline_noc(merged:dict)->str:
    if not isinstance(merged,dict) or merged.get("schema")!="aiops-noc-checkmk-merged-offline-v1":
        raise ValueError("unexpected Checkmk merged schema")
    if merged.get("provenance")!="UNVERIFIED_OFFLINE_EXPORTS" or merged.get("runtime_authenticated") is not False or merged.get("live_remediation_authorized") is not False:
        raise ValueError("forged runtime claim")
    hosts=merged.get("hosts")
    if not isinstance(hosts,dict) or not hosts or len(hosts)>500:
        raise ValueError("invalid hosts")
    esc=lambda v:html.escape(str(v),quote=True)
    rows=[]
    total=0
    for name,data in sorted(hosts.items()):
        if not isinstance(data,dict) or data.get("host_state") not in STATES or data.get("overall_state") not in STATES or not isinstance(data.get("services"),list):
            raise ValueError("invalid monitoring object")
        checks=data["services"]
        if len(checks)>500:raise ValueError("too many checks")
        total+=len(checks)
        cells=[]
        for service in checks:
            if not isinstance(service,dict) or service.get("state") not in STATES:
                raise ValueError("invalid service")
            cells.append("<li>"+esc(service.get("name",""))+" <strong>"+esc(service["state"])+"</strong> — "+esc(service.get("output",""))+"</li>")
        rows.append('<tr data-state="'+data["overall_state"]+'"><td>'+esc(name)+'</td><td>'+esc(data["host_state"])+'</td><td><strong>'+esc(data["overall_state"])+'</strong></td><td><details><summary>'+esc(len(checks))+' contrôles</summary><ul>'+"".join(cells)+"</ul></details></td></tr>")
    if merged.get("host_count")!=len(hosts) or merged.get("service_count")!=total:
        raise ValueError("forged monitoring totals")
    return """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIOps NOC — Export Checkmk non authentifié</title><style>
:root{color-scheme:dark;font:15px system-ui;background:#071725;color:#eaf4ff}
body{max-width:1200px;margin:25px auto;padding:12px}
header,section{background:#10263c;padding:20px;border:1px solid #2f4c65;border-radius:12px;margin-bottom:18px}
h1{margin:0}small{color:#b8d2e5}
table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:12px;border-bottom:1px solid #365064}
tr[data-state=CRIT]{border-left:4px solid #ec596b}tr[data-state=WARN]{border-left:4px solid #e9b84a}
button{background:#254663;color:white;border:1px solid #5b80a5;border-radius:6px;padding:8px}
tr[hidden]{display:none}details{max-width:500px}li{margin:7px 0}
</style></head><body><header><h1>AIOps NOC — État Checkmk exporté</h1>
<p>EXPORT HORS LIGNE NON AUTHENTIFIÉ · Aucune connexion live · Aucune remédiation</p>
<small>Capture : """+esc(merged.get("captured_at"))+""" · Âge à la validation : """+esc(merged.get("age_seconds"))+""" secondes</small></header>
<section><h2>Supervision hôtes &amp; services</h2>
<p>Hôtes : """+esc(len(hosts))+""" · Contrôles : """+esc(total)+"""</p>
<nav aria-label="Filtrer par criticité"><button type="button" data-filter="ALL">Tous</button>
<button type="button" data-filter="CRIT">CRIT</button><button type="button" data-filter="WARN">WARN</button>
<button type="button" data-filter="UNKNOWN">UNKNOWN</button><button type="button" data-filter="OK">OK</button></nav>
<table><thead><tr><th>Équipement</th><th>Disponibilité</th><th>État consolidé</th><th>Services</th></tr></thead>
<tbody>"""+"".join(rows)+"""</tbody></table></section>
<script>document.querySelectorAll('button[data-filter]').forEach(b=>b.addEventListener('click',()=>{
const state=b.dataset.filter;document.querySelectorAll('tbody tr').forEach(row=>{
row.hidden=state!=='ALL'&&row.dataset.state!==state;
});}));</script></body></html>"""

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("host_export",type=Path)
    parser.add_argument("service_export",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    host=json.loads(args.host_export.read_text(encoding="utf-8"))
    service=json.loads(args.service_export.read_text(encoding="utf-8"))
    page=render_checkmk_offline_noc(consolidate_checkmk_snapshot(host,service))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8") as f:f.write(page)

if __name__=="__main__":main()
