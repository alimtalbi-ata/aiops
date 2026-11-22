#!/usr/bin/env python3
"""ACME V2.12.4 offline dual-provenance presentation kit, no live access."""
import argparse,hashlib,html,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"tools"
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def checksum(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def index_html():
    return """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ACME | Demo Evidence Center</title>
<style>:root{color-scheme:dark;font-family:system-ui,Segoe UI,sans-serif;background:#071627;color:#edf7ff}body{max-width:1200px;margin:0 auto;padding:36px 24px;background:radial-gradient(ellipse at 95% 0,#1e5072,transparent 60%)}h1{font-size:clamp(2.4rem,5vw,4rem)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:22px}.card{background:#142d47;padding:23px;border:1px solid #416680;border-radius:16px}.label{color:#a8e6e0;font-weight:bold}.warning{background:#51361e;padding:15px;border-left:4px solid #ffd077;border-radius:10px}a{color:#b3ebff;font-weight:bold;font-size:1.1rem}a:focus-visible{outline:3px solid #ffd077}p{line-height:1.6;color:#d5e2ee}footer{margin-top:30px;color:#b4ccdd}</style></head>
<body><p>ACME DIGITAL TWIN · KIT HORS LIGNE</p><h1>Mission Control &amp; Evidence Center</h1><p>Deux parcours complémentaires pour expliquer une investigation et ses limites techniques.</p>
<p class="warning"><strong>PROVENANCES DIFFÉRENTES.</strong> Le cockpit métier est entièrement synthétique. Le rapport historique est un instantané de métadonnées communiquées par l'opérateur, et non une nouvelle lecture authentifiée de Core. Aucun de ces écrans ne prouve une inférence DGX indépendante ni une remédiation LIVE.</p>
<main class="grid"><section class="card"><p class="label">01 — SYNTHETIC · INTERACTIF</p><h2>Mission Control</h2><p>Six histoires métier fictives, topologie illustrative, sept événements par scénario, Analyst/Critic simulés et refus Policy narratif.</p>
<a href="ACME-MISSION-CONTROL.html">Explorer la simulation →</a></section>
<section class="card"><p class="label">02 — HISTORICAL AUDIT · SNAPSHOT</p><h2>Traçabilité du run Core</h2><p>Run historique RUN-A4449145A6E377FF : comptages Analyst/Critic/Policy, rapprochement des références Evidence et limites de validation.</p>
<a href="ACME-HISTORICAL-AUDIT.html">Examiner les métadonnées →</a></section></main>
<footer>Kit HTML local sans requêtes réseau ni opérations sur l'infrastructure. Ce dossier ne comporte aucun export brut de prompts ou de secrets.</footer></body></html>"""
def build(input_file,output):
    audit=load("export_acme_historical_audit_v2123")
    mission=load("export_acme_mission_control_v2119")
    source=audit.validate(json.loads(input_file.read_text(encoding="utf-8")))
    output.mkdir(parents=True,exist_ok=True)
    pages={
      "index.html":index_html(),
      "ACME-MISSION-CONTROL.html":mission.build(mission.dataset()),
      "ACME-HISTORICAL-AUDIT.html":audit.render(source)}
    for name,content in pages.items(): (output/name).write_text(content,encoding="utf-8")
    manifest={"version":"2.12.4","mode":"OFFLINE_MIXED_SEPARATED",
      "historical_source":"OPERATOR_SUPPLIED_SUMMARY_NOT_INDEPENDENTLY_AUTHENTICATED",
      "synthetic_scenarios":6,"dgx_independently_attested":False,
      "live_execution_qualified":False,"network_required":False,
      "files":[{"name":name,"sha256":checksum(output/name)} for name in pages]}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return manifest
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--input",required=True,type=Path);p.add_argument("--output",type=Path,default=Path("/tmp/acme-evidence-center-v2124"))
    a=p.parse_args();print(json.dumps(build(a.input,a.output),indent=2,ensure_ascii=False))
