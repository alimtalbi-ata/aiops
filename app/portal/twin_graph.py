"""Pure, dependency-free Digital Twin graph view.

Rendering is client-side SVG with textContent (never user-controlled innerHTML).
Graph is limited to keep client work bounded; long inventories remain in tables.
"""
import json
from html import escape

def graph_panel(graph, max_nodes=120, max_edges=300, impact=None):
    if not isinstance(graph,dict):
        return '<p class="muted">INCONNU — graphe indisponible.</p>'
    nodes=graph.get("nodes")
    edges=graph.get("edges")
    if not isinstance(nodes,list) or not isinstance(edges,list):
        return '<p class="muted">INCONNU — graphe indisponible.</p>'
    ids=set()
    safe_nodes=[]
    for n in nodes[:max_nodes]:
        if not isinstance(n,dict): continue
        identifier=str(n.get("node_id",""))
        if not identifier or identifier in ids: continue
        ids.add(identifier)
        safe_nodes.append({k:n.get(k) for k in ("node_id","name","type","site","state")})
    safe_edges=[]
    for e in edges[:max_edges]:
        if not isinstance(e,dict): continue
        source=str(e.get("source_id",""))
        target=str(e.get("target_id",""))
        if source in ids and target in ids and source!=target:
            safe_edges.append({"source_id":source,"target_id":target,"relation_type":e.get("relation_type")})
    affected = impact.get("affected",[]) if isinstance(impact,dict) else []
    impact_known = isinstance(affected,list) and isinstance(impact,dict) and isinstance(impact.get("root"),str)
    impact_ids = [str(row.get("node_id")) for row in affected if isinstance(row,dict) and row.get("node_id") in ids] if impact_known else []
    payload=json.dumps({"nodes":safe_nodes,"edges":safe_edges,"impact_ids":impact_ids,"impact_known":impact_known},ensure_ascii=True,separators=(",",":")).replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
    return '''<section class="panel" aria-label="Graphe de dépendances">
<h2>Topologie interactive</h2><p class="muted">Données du registre Twin, sous-ensemble borné : %d nœuds / %d relations. Sélectionnez un nœud pour voir ses dépendances directes. Impact issu du calcul Twin, si disponible.</p>
<div class="graph-controls"><button type="button" id="graph-reset" class="secondary">Réinitialiser</button>
<label for="graph-filter">Recherche :</label><input id="graph-filter" type="search" placeholder="Nœud ou nom">\n<label for="graph-site">Site :</label><select id="graph-site"><option value="">Tous les sites</option></select>\n<label for="graph-state">État :</label><select id="graph-state"><option value="">Tous les états</option></select>\n<button id="graph-zoom-in" type="button" aria-label="Zoom avant">＋</button><button id="graph-zoom-out" type="button" aria-label="Zoom arrière">－</button>
</div><svg id="twin-graph" role="img" aria-label="Graphe orienté des dépendances ACME" viewBox="0 0 900 520" style="width:100%%;min-height:320px;background:var(--bg);border-radius:12px;border:1px solid var(--line)"></svg>
<p id="graph-detail" role="status" aria-live="polite">Sélectionner un nœud du graphe.</p></section>
<script id="twin-graph-data" type="application/json">%s</script>
<script>
(function(){
"use strict";
const raw=document.getElementById("twin-graph-data");
const svg=document.getElementById("twin-graph");
if(!raw||!svg)return;
const data=JSON.parse(raw.textContent);
const NS="http://www.w3.org/2000/svg";
const detail=document.getElementById("graph-detail");
const lookup=new Map(data.nodes.map(n=>[String(n.node_id),n]));
const impact=new Set(data.impact_ids||[]);\nconst siteInput=document.getElementById("graph-site");\nconst stateInput=document.getElementById("graph-state");\nlet scale=1;\nfor(const [control,key] of [[siteInput,"site"],[stateInput,"state"]]){\nfor(const value of [...new Set(data.nodes.map(n=>String(n[key]||"INCONNU")))].sort()){const option=document.createElement("option");option.value=value;option.textContent=value;control.append(option);}\n}
function elem(name,attrs,text){
const el=document.createElementNS(NS,name);
for(const [key,value] of Object.entries(attrs||{}))el.setAttribute(key,String(value));
if(text!==undefined)el.textContent=String(text);
return el;
}
function draw(){
svg.replaceChildren();
const query=document.getElementById("graph-filter").value.trim().toLowerCase();
const site=siteInput.value,state=stateInput.value;
const shown=data.nodes.filter(n=>
(!query||String(n.name||n.node_id).toLowerCase().includes(query))&&
(!site||String(n.site||"INCONNU")===site)&&
(!state||String(n.state||"INCONNU")===state)
).slice(0,120);
const w=900/scale,h=520/scale;
svg.setAttribute("viewBox",String((900-w)/2)+" "+String((520-h)/2)+" "+String(w)+" "+String(h));
const cols=Math.max(1,Math.ceil(Math.sqrt(shown.length*1.7)));
const rows=Math.max(1,Math.ceil(shown.length/cols));
const xy=new Map();
shown.forEach((n,i)=>{const c=i%%cols,r=Math.floor(i/cols);
xy.set(String(n.node_id),[65+(770*(c+.5)/cols),45+(425*(r+.5)/rows)]);
});
const defs=elem("defs");const marker=elem("marker",{id:"twin-arrow",viewBox:"0 0 10 10",refX:9,refY:5,markerWidth:5,markerHeight:5,orient:"auto-start-reverse"});
marker.append(elem("path",{d:"M 0 0 L 10 5 L 0 10 z",fill:"#7F77DD"}));defs.append(marker);svg.append(defs);
for(const e of data.edges){const a=xy.get(String(e.source_id)),b=xy.get(String(e.target_id));if(!a||!b)continue;
svg.append(elem("line",{x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:"#7F77DD","stroke-width":1.7,"marker-end":"url(#twin-arrow)",opacity:.65}));
}
for(const n of shown){
const [x,y]=xy.get(String(n.node_id));
const state=String(n.state||"UNKNOWN").toUpperCase();
const color=state==="FAILED"?"#E24B4A":state==="DEGRADED"?"#EF9F27":"#1D9E75";
const group=elem("g",{tabindex:"0",role:"button","aria-label":String(n.name||n.node_id),"data-node-id":n.node_id});
group.append(elem("circle",{cx:x,cy:y,r:19,fill:color,stroke:impact.has(String(n.node_id))?"#D4537E":"#ffffff","stroke-width":impact.has(String(n.node_id))?5:2}));
group.append(elem("text",{x,y:y+31,"text-anchor":"middle",fill:"currentColor","font-size":11},String(n.name||n.node_id).slice(0,25)));
const select=()=>{const id=String(n.node_id);const links=data.edges.filter(e=>String(e.source_id)===id||String(e.target_id)===id);
detail.textContent=String(n.name||id)+" ("+state+") · "+links.length+" relation(s) directes · "+String(n.type||"INCONNU")+" · impact calculé : "+(data.impact_known?(impact.has(id)?"OUI":"NON"):"INCONNU");};
group.addEventListener("click",select);
group.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();select();}});
svg.append(group);
}
if(!shown.length){detail.textContent="Aucun nœud correspondant à la recherche.";}
}
draw();
document.getElementById("graph-filter").addEventListener("input",draw);
siteInput.addEventListener("change",draw);
stateInput.addEventListener("change",draw);
document.getElementById("graph-zoom-in").addEventListener("click",()=>{scale=Math.min(3,scale*1.25);draw();});
document.getElementById("graph-zoom-out").addEventListener("click",()=>{scale=Math.max(0.65,scale/1.25);draw();});
document.getElementById("graph-reset").addEventListener("click",()=>{document.getElementById("graph-filter").value="";siteInput.value="";stateInput.value="";scale=1;draw();detail.textContent="Sélectionner un nœud du graphe.";});
})();
</script>''' % (len(safe_nodes),len(safe_edges),payload)
