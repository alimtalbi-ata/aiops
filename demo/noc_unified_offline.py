"""Unified offline NOC page: synthetic demo and unverified Checkmk separated."""
from __future__ import annotations
import argparse
import html
import json
from pathlib import Path
from demo.noc_wallboard import render_noc_wallboard
from demo.noc_checkmk_offline_wallboard import render_checkmk_offline_noc
from demo.noc_synthetic_snapshot import build_noc_snapshot
from demo.noc_checkmk_consolidation import consolidate_checkmk_snapshot

def render_unified_noc(catalog:dict,host_export:dict,service_export:dict)->str:
    synthetic=render_noc_wallboard(build_noc_snapshot(catalog),catalog)
    observed=render_checkmk_offline_noc(consolidate_checkmk_snapshot(host_export,service_export))
    # Embed as separate sandboxed documents so JS, CSS and runtime provenance
    # from either page cannot affect or disguise the other.
    left=html.escape(synthetic,quote=True)
    right=html.escape(observed,quote=True)
    return """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIOps — NOC unifié hors ligne</title><style>
:root{color-scheme:dark;font:15px system-ui;background:#071321;color:white}
body{margin:0;padding:18px}h1{margin:0 0 10px}p{color:#bed4e5}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}
section{background:#132a40;border:1px solid #395873;border-radius:12px;padding:12px}
iframe{width:100%;height:750px;border:1px solid #54718a;border-radius:8px;background:white}
mark{padding:3px 7px;background:#72561e;color:#fff}
</style></head><body>
<h1>AIOps — NOC Command Center</h1>
<p><mark>MODE HORS LIGNE · SOURCES NON AUTHENTIFIÉES</mark> Les vues restent séparées :
la simulation n'est jamais fusionnée avec des mesures exportées.</p>
<main><section><h2>Scénario ACME — SYNTHÉTIQUE</h2>
<iframe sandbox="allow-scripts" title="NOC scénario synthétique" srcdoc=""""+left+""""></iframe></section>
<section><h2>Checkmk — EXPORT NON AUTHENTIFIÉ</h2>
<iframe sandbox="allow-scripts" title="NOC Checkmk hors ligne" srcdoc=""""+right+""""></iframe></section></main>
<p>Aucune requête réseau, authentification ou action LIVE n'est effectuée.</p></body></html>"""

def main():
    p=argparse.ArgumentParser()
    p.add_argument("host_export",type=Path)
    p.add_argument("service_export",type=Path)
    p.add_argument("--catalog",type=Path,default=Path(__file__).with_name("rag_ops_fixture_catalog.json"))
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    page=render_unified_noc(json.loads(args.catalog.read_text(encoding="utf-8")),
                            json.loads(args.host_export.read_text(encoding="utf-8")),
                            json.loads(args.service_export.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8") as f:f.write(page)
if __name__=="__main__":main()
