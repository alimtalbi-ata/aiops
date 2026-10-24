"""Render a validated OFFLINE_TEST NOC evidence index as inert HTML."""
from __future__ import annotations
import html
import re

EXPECTED={"noc-offline-unified":"unified.png","noc-offline-synthetic":"synthetic.png",
          "noc-offline-checkmk-export":"checkmk-export.png"}
HEX=re.compile(r"^[0-9a-f]{64}$")

def render_noc_evidence_center(index:dict)->str:
    if not isinstance(index,dict) or index.get("schema")!="aiops-noc-evidence-index-v1" or index.get("runtime_authenticated") is not False or index.get("live_remediation_authorized") is not False:
        raise ValueError("untrusted evidence index")
    if index.get("counts")!={"OFFLINE_TEST":3,"OBSERVATION":0,"RUNTIME_EVIDENCE":0}:
        raise ValueError("unverified evidence classes")
    entries=index.get("entries")
    if not isinstance(entries,list) or len(entries)!=3:
        raise ValueError("invalid evidence count")
    seen=set();rows=[]
    for entry in entries:
        if not isinstance(entry,dict) or entry.get("id") not in EXPECTED or entry.get("file")!=EXPECTED.get(entry.get("id")) or entry["id"] in seen:
            raise ValueError("invalid evidence reference")
        seen.add(entry["id"])
        if (entry.get("class")!="OFFLINE_TEST" or entry.get("source")!="LOCAL_OFFLINE_BROWSER_RENDER"
                or entry.get("runtime_authenticated") is not False or entry.get("promotable_to_runtime") is not False
                or type(entry.get("size_bytes")) is not int or entry["size_bytes"]<=100
                or not isinstance(entry.get("sha256"),str) or not HEX.fullmatch(entry["sha256"])):
            raise ValueError("untrusted evidence metadata")
        esc=lambda value:html.escape(str(value),quote=True)
        rows.append("<tr><td>"+esc(entry["file"])+"</td><td>OFFLINE_TEST</td><td><code>"+esc(entry["sha256"])+"</code></td><td>"+esc(entry["size_bytes"])+"</td></tr>")
    if seen!=set(EXPECTED):
        raise ValueError("missing expected evidence")
    return """<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>AIOps — Centre de preuves NOC</title>
<style>:root{color-scheme:dark;background:#071625;color:#e9f3ff;font:15px system-ui}body{margin:30px auto;max-width:1200px;padding:15px}
section{background:#122b42;border-radius:12px;padding:22px;margin:15px 0;border:1px solid #37566d}
table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:12px;border-bottom:1px solid #36546d}
code{word-break:break-all}strong{color:#ffd38f}</style></head><body><h1>AIOps — Centre de preuves NOC</h1>
<section><strong>OFFLINE_TEST uniquement — aucune preuve de production</strong>
<p>Trois captures de navigateur hors ligne. OBSERVATION : 0 · RUNTIME_EVIDENCE : 0</p>
<p>Source : scénarios synthétiques et exports Checkmk non authentifiés. Aucune promotion LIVE.</p></section>
<section><h2>Inventaire des captures vérifiées</h2><table><thead><tr><th>Fichier</th><th>Classe</th><th>SHA-256</th><th>Octets</th></tr></thead>
<tbody>"""+"".join(rows)+"""</tbody></table></section></body></html>"""
