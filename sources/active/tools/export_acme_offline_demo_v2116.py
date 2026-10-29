#!/usr/bin/env python3
"""Generate standalone ACME demo HTML from the repository catalog; no network or effects."""
import argparse,hashlib,html,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load_stories(source=ROOT/"app/portal/acme_stories.py"):
    spec=importlib.util.spec_from_file_location("acme_offline_catalog",source)
    if spec is None or spec.loader is None:raise ValueError("missing catalog")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    stories=module.STORIES
    required={"id","title","persona","business_impact","service","symptom","hypothesis","control","outcome","status"}
    if len(stories)!=6 or any(not isinstance(s,dict) or not required.issubset(s) or not all(isinstance(s[k],str) and s[k] for k in required) for s in stories):raise ValueError("invalid six-story catalog")
    if len({s["id"] for s in stories})!=len(stories):raise ValueError("duplicate story ids")
    return stories
def build_html(stories):
    cards=[]
    for i,s in enumerate(stories):
        v=lambda key:html.escape(s[key],quote=True)
        provenance=("RUN HISTORIQUE — vérifier la timeline d’origine" if s["status"]=="HISTORICAL_DGX" else "ÉVALUATION SYNTHÉTIQUE — sans inférence DGX prouvée" if s["status"]=="BENCHMARK_ONLY" else "SCÉNARIO FICTIF — non exécuté")
        details="".join("<dt>"+name+"</dt><dd>"+v(key)+"</dd>" for name,key in [("Personne","persona"),("Service","service"),("Symptôme","symptom"),("Hypothèse à vérifier","hypothesis"),("Contrôle","control"),("Résultat présenté","outcome")])
        cards.append(f'<article class="story"><button class="story-choice" aria-expanded="false" aria-controls="details-{i}"><small>{html.escape(provenance)}</small><strong>{v("title")}</strong><span>{v("business_impact")}</span></button><section id="details-{i}" hidden><dl>{details}</dl></section></article>')
    return """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ACME | AIOps hors ligne</title><style>
:root{color-scheme:dark;font-family:system-ui,Segoe UI,sans-serif;background:#0a1525;color:#f5f7fc}body{margin:0 auto;max-width:1160px;padding:35px 22px;background:radial-gradient(ellipse at 80% 0,#174368 0,transparent 60%)}h1{font-size:clamp(2rem,5vw,3.8rem)}p{line-height:1.55;color:#c7d5e6}.notice{padding:15px;background:#352c1b;border-left:4px solid #f6b65c;border-radius:8px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin:24px 0}.story{border:1px solid #35536f;background:#10263d;border-radius:15px;overflow:hidden}.story-choice{display:flex;flex-direction:column;gap:12px;width:100%;padding:20px;text-align:left;background:none;border:0;color:inherit;cursor:pointer;font:inherit}.story-choice:focus-visible{outline:3px solid #80dbff}.story-choice strong{font-size:1.22rem}.story-choice small{color:#a4f0e3;font-weight:bold}.story section{padding:0 20px 18px}dt{font-weight:bold;color:#a4f0e3;margin-top:10px}dd{margin:3px 0}footer{border-top:1px solid #35536f}</style></head><body><header><p>ACME DIGITAL TWIN · AIOps 2.0</p><h1>Une panne. Plusieurs signaux. Une décision contrôlée.</h1><p>Six histoires pour explorer les impacts métier et le contrôle de l'autonomie.</p><p class="notice"><strong>DÉMONSTRATION HORS LIGNE.</strong> Aucun contact avec DGX, la CMDB ou les équipements. Un run historique externe est référencé : RUN-A4449145A6E377FF. Aucune approbation humaine ou remédiation LIVE n'est effectuée.</p></header><main><h2>Choisissez un scénario</h2><div class="grid">"""+'\n'.join(cards)+"""</div></main><footer><p>Source : catalogue ACME. Hypothèses non confirmées tant que les preuves ne les corroborent pas. Les exécuteurs LIVE ne sont pas qualifiés.</p></footer><script>
for(const button of document.querySelectorAll('.story-choice')){button.addEventListener('click',()=>{const panel=document.getElementById(button.getAttribute('aria-controls'));const open=button.getAttribute('aria-expanded')==='true';button.setAttribute('aria-expanded',String(!open));panel.hidden=open;});}
</script></body></html>"""
def export(directory,stories):
    directory.mkdir(parents=True,exist_ok=True)
    page=directory/"ACME-OFFLINE-DEMO.html";page.write_text(build_html(stories),encoding="utf-8")
    manifest={"mode":"OFFLINE_SYNTHETIC","effects":"NONE","catalog_count":len(stories),"files":[{"name":page.name,"sha256":hashlib.sha256(page.read_bytes()).hexdigest()}],"historic_dgx_run_reference":"RUN-A4449145A6E377FF"}
    (directory/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return page,manifest
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,default=Path("/tmp/acme-offline-demo-v2116"));args=p.parse_args()
    page,manifest=export(args.output,load_stories());print(json.dumps({"page":str(page),**manifest},ensure_ascii=False,indent=2))
