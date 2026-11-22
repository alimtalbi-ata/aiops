#!/usr/bin/env python3
"""ACME V2.12.3: offline historical audit panel from explicitly supplied metadata.
No Core access, no secrets, no fabricated model outputs.
"""
import argparse,hashlib,html,json
from pathlib import Path

REQUIRED=("run_id","run_status","run_mode","events","stages","evidence_records",
"analyst_records","critic_records","policy_decisions","analyst_evidence",
"critic_evidence","event_evidence","critic_validation_declarations","policy_decision_states")
def validate(data):
    if not isinstance(data,dict) or any(k not in data for k in REQUIRED):
        raise ValueError("missing historical audit fields")
    if data["run_id"]!="RUN-A4449145A6E377FF":
        raise ValueError("unrecognized historical run")
    for k in ("events","stages","evidence_records","analyst_records","critic_records","policy_decisions"):
        if type(data[k]) is not int or data[k]<0:raise ValueError("invalid count: "+k)
    for key in ("analyst_evidence","critic_evidence","event_evidence"):
        v=data[key]
        if not isinstance(v,dict) or any(type(v.get(k)) is not int or v[k]<0 for k in ("references","found_in_export","missing_from_export")):
            raise ValueError("bad references: "+key)
        if v["references"]!=v["found_in_export"]+v["missing_from_export"]:
            raise ValueError("inconsistent references")
    if not isinstance(data["critic_validation_declarations"],dict) or not isinstance(data["policy_decision_states"],dict):
        raise ValueError("invalid decisions")
    if data.get("dgx_independently_attested") is not False or data.get("live_execution_qualified") is not False:
        raise ValueError("independent qualification unsupported")
    return data
def render(data):
    d=validate(data)
    e=lambda v:html.escape(str(v),quote=True)
    rows="".join("<tr><th>"+e(name)+"</th><td>"+e(d[key])+"</td></tr>" for name,key in
       [("Mode","run_mode"),("État du run","run_status"),("Événements","events"),
       ("Étapes","stages"),("Preuves du run","evidence_records"),("Analyst","analyst_records"),
       ("Critic","critic_records"),("Décisions Policy","policy_decisions")])
    cross="".join("<tr><th>"+e(label)+"</th><td>"+e(d[key]["references"])+"</td><td>"+e(d[key]["found_in_export"])+"</td><td>"+e(d[key]["missing_from_export"])+"</td></tr>"
      for label,key in [("Analyst","analyst_evidence"),("Critic","critic_evidence"),("Événements","event_evidence")])
    critic=", ".join(e(k)+": "+e(v) for k,v in sorted(d["critic_validation_declarations"].items()))
    policy=", ".join(e(k)+": "+e(v) for k,v in sorted(d["policy_decision_states"].items()))
    return """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ACME — Audit historique</title><style>:root{color-scheme:dark;font:16px system-ui;background:#0b1828;color:#edf4ff}body{margin:30px auto;max-width:1000px;padding:0 20px}h1{font-size:2.4rem}.notice{border-left:4px solid #ffc56c;background:#433019;padding:14px;border-radius:9px}table{width:100%;border-collapse:collapse;margin:18px 0}th,td{border-bottom:1px solid #42556b;text-align:left;padding:11px}th{color:#b8e8df}section{background:#132b45;border-radius:14px;padding:18px;margin:18px 0}p{line-height:1.5}</style></head>
<body><h1>Audit du run historique <code>"""+e(d["run_id"])+"""</code></h1>
<p class="notice"><strong>MÉTADONNÉES D'UN AUDIT OPÉRATEUR.</strong> Ces chiffres sont ceux d'un contrôle précédemment exécuté sur Core, sans réinterrogation dans cette page. Ils ne prouvent ni inférence DGX authentifiée ni blocage effectif d'un exécuteur LIVE.</p>
<section><h2>Registres historiques</h2><table>"""+rows+"""</table></section>
<section><h2>Rapprochement des identifiants de preuves</h2><table><thead><tr><th>Origine</th><th>Références</th><th>Trouvées</th><th>Absentes</th></tr></thead><tbody>"""+cross+"""</tbody></table><p>Une référence trouvée indique une cohérence du registre, pas une causalité attestée.</p></section>
<section><h2>Décisions enregistrées</h2><p>Déclarations Critic : <strong>"""+critic+"""</strong></p><p>États Policy : <strong>"""+policy+"""</strong></p></section>
<section><h2>Ce que nous ne pouvons pas conclure</h2><p>Une sortie Analyst, Critic ou Policy enregistrée ne constitue ni une preuve cryptographique d'inférence DGX, ni une approbation humaine, ni une preuve d'interception au dernier point d'effet. Le run lui-même est en mode DEMO.</p>
<p>La carte de dépendances et la timeline synthétiques ACME constituent une démonstration distincte de cet audit.</p></section></body></html>"""
def export(source,out):
    report=validate(json.loads(source.read_text(encoding="utf-8")))
    out.mkdir(parents=True,exist_ok=True)
    page=out/"ACME-HISTORICAL-AUDIT.html"
    page.write_text(render(report),encoding="utf-8")
    summary={"version":"2.12.3","mode":"OFFLINE_HISTORICAL_AUDIT","source_authenticated":False,
      "dgx_independently_attested":False,"live_effects_verified":False,"sha256":hashlib.sha256(page.read_bytes()).hexdigest()}
    (out/"manifest.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return summary
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--output",type=Path,default=Path("/tmp/acme-audit-v2123"));a=p.parse_args()
    print(json.dumps(export(a.input,a.output),indent=2,ensure_ascii=False))
