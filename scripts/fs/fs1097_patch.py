#!/usr/bin/env python3
"""FS1097: add CSP-hashed, same-origin Prometheus history charts to candidate UI."""
import ast, base64, hashlib, pathlib, re

html_path = pathlib.Path("/app/portal/fs1051_visual.html")
api_path = pathlib.Path("/app/portal/fs1051_visual.py")
html = html_path.read_text(encoding="utf-8")
api = api_path.read_text(encoding="utf-8")

assert 'id="history-chart"' not in html
style_match = re.search(r"<style>(.*?)</style>", html, re.S)
script_match = re.search(r"<script>(.*?)</script>", html, re.S)
assert style_match and script_match

css_add = """
.history-controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:12px 0}
.history-controls label{display:flex;gap:8px;align-items:center;color:#a7b9d0}
.history-controls select{background:#0b1628;border:1px solid #41546e;border-radius:8px;padding:9px;color:#fff}
.history-chart{width:100%;height:auto;min-height:260px;max-height:420px;background:#0b1729;border-radius:10px}
.history-legend{display:flex;gap:14px;flex-wrap:wrap;margin:10px 0;color:#c8d8ea;font-size:13px}
.history-legend span{display:inline-flex;gap:6px;align-items:center}
.history-legend i{display:inline-block;width:12px;height:4px;border-radius:4px}
.history-swatch-0{background:#62c6ff}.history-swatch-1{background:#64ddb0}.history-swatch-2{background:#ffbd69}.history-swatch-3{background:#d7a5ff}.history-swatch-4{background:#ff929c}.history-swatch-5{background:#9bd3ae}
.history-status{min-height:1.5em;color:#a7b9d0}
.history-axis{fill:#9fb3cd;font-size:11px}
.history-grid{stroke:#344a63;stroke-width:1;opacity:.7}
@media(max-width:600px){.history-controls{align-items:stretch}.history-controls label{width:100%;justify-content:space-between}.history-controls select{min-width:130px}.history-chart{min-height:220px}}
"""
html = html.replace("</style>", css_add + "</style>", 1)
section = """
<section class="card" aria-labelledby="history-title">
<h2 id="history-title">Historique Prometheus</h2>
<p class="muted">Séries temporelles réelles · lecture seule · source Prometheus</p>
<div class="history-controls">
<label for="history-metric">Métrique
<select id="history-metric"><option value="availability">Disponibilité (up)</option><option value="scrape_duration">Durée de scraping</option></select></label>
<label for="history-window">Période
<select id="history-window"><option value="1h">1 heure</option><option value="6h">6 heures</option><option value="24h">24 heures</option></select></label>
<button id="history-refresh" type="button">Actualiser l’historique</button>
</div>
<p id="history-status" class="history-status" role="status" aria-live="polite">Sélectionnez une métrique ou chargez l’historique.</p>
<div id="history-legend" class="history-legend" aria-label="Légende des séries"></div>
<svg id="history-chart" class="history-chart" viewBox="0 0 900 320" role="img" aria-label="Graphique temporel des métriques Prometheus">
<text x="450" y="160" text-anchor="middle" class="history-axis">Chargement de l’historique…</text>
</svg>
</section>
"""
html = html.replace('<button id="refresh">Actualiser</button></main>', '<button id="refresh">Actualiser</button>' + section + '</main>', 1)
assert 'id="history-chart"' in html
js_add = r"""
// FS1097: bounded same-origin historical series chart; no third-party assets.
// Cancel stale requests so rapid metric/window changes cannot append duplicate legends.
let historyRequestId=0,historyAbortController=null;
const historyColors=["#62c6ff","#64ddb0","#ffbd69","#d7a5ff","#ff929c","#9bd3ae"];
function historyElement(tag,attrs,text){const e=document.createElementNS("http://www.w3.org/2000/svg",tag);Object.entries(attrs||{}).forEach(([k,v])=>e.setAttribute(k,String(v)));if(text!==undefined)e.textContent=text;return e}
function historyTime(ts){return new Date(ts*1000).toLocaleTimeString("fr-FR",{hour:"2-digit",minute:"2-digit"})}
async function loadHistory(){
 const requestId=++historyRequestId;
 if(historyAbortController)historyAbortController.abort();
 const controller=new AbortController();historyAbortController=controller;
 const metric=$("history-metric").value,windowSize=$("history-window").value;
 const status=$("history-status"),chart=$("history-chart"),legend=$("history-legend"),button=$("history-refresh");
 button.disabled=true;status.textContent="Chargement des séries historiques…";legend.replaceChildren();
 chart.replaceChildren(historyElement("text",{x:450,y:160,"text-anchor":"middle",class:"history-axis"},"Chargement…"));
 try{
  const url="/api/fs1089/prometheus/history?"+new URLSearchParams({metric,window:windowSize});
  const response=await fetch(url,{credentials:"same-origin",headers:{Accept:"application/json"},signal:controller.signal});
  if(requestId!==historyRequestId)return;
  if(!response.ok)throw new Error("HTTP "+response.status);
  const data=await response.json();
  if(requestId!==historyRequestId)return;
  if(data.metric!==metric||data.window!==windowSize||!Array.isArray(data.series))throw new Error("Contrat de données invalide");
  // A repeated target in an upstream payload must not create a duplicate legend.\n  // Keep the first occurrence, preserving the server order and the five-target contract.\n  const seenTargets=new Set();\n  const series=data.series.filter(s=>{\n   if(!s||!Array.isArray(s.points)||!s.points.length)return false;\n   const key=JSON.stringify([s.job??null,s.instance??null]);\n   if(seenTargets.has(key))return false;\n   seenTargets.add(key);return true;\n  }).slice(0,30);
  const points=series.flatMap(s=>s.points).filter(p=>Array.isArray(p)&&p.length===2&&Number.isFinite(Number(p[0]))&&Number.isFinite(Number(p[1])));
  chart.replaceChildren();
  if(!points.length){chart.append(historyElement("text",{x:450,y:160,"text-anchor":"middle",class:"history-axis"},"Aucune donnée disponible pour cette période"));status.textContent="Aucune série avec points disponibles.";return}
  const width=900,height=320,left=64,right=18,top=18,bottom=42,plotW=width-left-right,plotH=height-top-bottom;
  let minT=Math.min(...points.map(p=>Number(p[0]))),maxT=Math.max(...points.map(p=>Number(p[0])));
  let minV=Math.min(...points.map(p=>Number(p[1]))),maxV=Math.max(...points.map(p=>Number(p[1])));
  if(minT===maxT)maxT=minT+1;if(minV===maxV){minV-=.5;maxV+=.5}
  const x=t=>left+(Number(t)-minT)/(maxT-minT)*plotW,y=v=>top+(maxV-Number(v))/(maxV-minV)*plotH;
  for(let i=0;i<=4;i++){const yy=top+i*plotH/4,val=maxV-i*(maxV-minV)/4;chart.append(historyElement("line",{x1:left,y1:yy,x2:width-right,y2:yy,class:"history-grid"}));chart.append(historyElement("text",{x:left-9,y:yy+4,"text-anchor":"end",class:"history-axis"},Number(val.toPrecision(3)).toString()))}
  for(let i=0;i<=4;i++){const xx=left+i*plotW/4,stamp=minT+i*(maxT-minT)/4;chart.append(historyElement("text",{x:xx,y:height-13,"text-anchor":"middle",class:"history-axis"},historyTime(stamp)))}
  series.forEach((s,index)=>{
   const valid=s.points.filter(p=>Array.isArray(p)&&p.length===2&&Number.isFinite(Number(p[0]))&&Number.isFinite(Number(p[1])));
   if(!valid.length)return;
   const color=historyColors[index%historyColors.length],d=valid.map((p,i)=>(i?"L":"M")+x(p[0]).toFixed(2)+" "+y(p[1]).toFixed(2)).join(" ");
   chart.append(historyElement("path",{d,fill:"none",stroke:color,"stroke-width":2.2,"stroke-linejoin":"round","stroke-linecap":"round"}));
   const name=[s.job,s.instance].filter(Boolean).join(" · ")||("Série "+(index+1));
   const item=document.createElement("span"),swatch=document.createElement("i"),label=document.createElement("span");swatch.className="history-swatch history-swatch-"+(index%historyColors.length);label.textContent=name;item.append(swatch,label);legend.append(item);
  });
  status.textContent=series.length+" séries · "+points.length+" points · pas "+data.step_seconds+" s · "+windowSize;
 }catch(error){if(requestId!==historyRequestId||error.name==="AbortError")return;chart.replaceChildren(historyElement("text",{x:450,y:160,"text-anchor":"middle",class:"history-axis"},"Historique indisponible"));status.textContent="Erreur de chargement : "+error.message}
 finally{if(requestId===historyRequestId){button.disabled=false;if(historyAbortController===controller)historyAbortController=null}}
}
$("history-refresh").addEventListener("click",loadHistory);
$("history-metric").addEventListener("change",loadHistory);
$("history-window").addEventListener("change",loadHistory);
loadHistory();
"""
script_match = re.search(r"<script>(.*?)</script>", html, re.S)
assert script_match
html = html[:script_match.end()-9] + js_add + html[script_match.end()-9:]
html_path.write_text(html, encoding="utf-8")

def csp_hash(value):
    digest = base64.b64encode(hashlib.sha256(value.encode("utf-8")).digest()).decode()
    return "'sha256-" + digest + "'"
style = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
script = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
new_script, new_style = csp_hash(script), csp_hash(style)
updated, count = re.subn(r"script-src 'sha256-[^']+'; style-src 'sha256-[^']+'",
                         "script-src " + new_script + "; style-src " + new_style, api)
assert count == 1, "Expected exactly one existing response CSP hash pair"
ast.parse(updated)
api_path.write_text(updated, encoding="utf-8")
print("FS1097_UI_PATCH=PASS")
print("FS1097_CSP_HASHES=RECOMPUTED")
print("FS1097_HISTORY_CHART=PASS")
