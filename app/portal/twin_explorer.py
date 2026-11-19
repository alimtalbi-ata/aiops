"""Integrated synthetic-only Twin module; no shared topology disclosure."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from twin.dependents import potential_dependents

router = APIRouter()
def snapshot():
    ids = ["ACME-SAN-FABRIC-A","ACME-SAN-FABRIC-B","DEMO-STORAGE","DEMO-VM","DEMO-PAYMENTS"]
    nodes = [{"node_id":n,"name":n,"state":"DEGRADED" if i==0 else "HEALTHY"} for i,n in enumerate(ids)]
    links = [(2,0),(2,1),(3,2),(4,3)]
    return {"nodes":nodes,"edges":[{"edge_id":f"DEMO-E{i}","source_id":ids[a],"target_id":ids[b],"relation_type":"DEPENDS_ON"} for i,(a,b) in enumerate(links)]}

@router.get("/api/demo/twin/graph")
def graph():
    return snapshot()

@router.get("/api/demo/twin/dependents/{node_id}")
def dependents(node_id: str):
    try:
        return potential_dependents(snapshot(),node_id)
    except KeyError:
        raise HTTPException(404,"Unknown synthetic node")

@router.get("/demo/twin")
def index():
    return HTMLResponse(PAGE,headers={"Cache-Control":"no-store","Content-Security-Policy":"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"})

PAGE = r"""<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIOps2 Twin Explorer</title><style>
body{font:16px system-ui;background:#111827;color:#e5e7eb;margin:32px} main{max-width:1250px;margin:auto} select,button{padding:12px;background:#263449;color:white;border:1px solid #64748b;border-radius:6px} table{width:100%;border-collapse:collapse} td,th{text-align:left;padding:12px;border-bottom:1px solid #374151} td{overflow-wrap:anywhere} section{background:#1f2937;padding:20px;margin:20px 0;border-radius:8px} small{color:#a5b4fc} pre{white-space:pre-wrap} .bad{color:#fca5a5}
</style><main><nav><a href="/" style="color:white">Mission Control</a> · <a href="/demo/studio" style="color:white">Demo Studio</a></nav><h1>AIOps2 | Twin Explorer</h1><p>DEMO · SYNTHÉTIQUE · LECTURE SEULE · aucune causalité confirmée</p>
<section><label for="root">Équipement source </label><select id="root"></select> <button id="run">Calculer les dépendants</button> <button id="compare">Comparer Fabric A/B</button><p id="summary" role="status"></p></section>
<section><h2>Impact potentiel</h2><table><thead><tr><th>Profondeur</th><th>CI</th><th>État</th><th>Chemin de preuve</th></tr></thead><tbody id="rows"></tbody></table><pre id="details"></pre></section>
<script>
const el=id=>document.getElementById(id);
async function get(url){const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);return r.json()}
async function calculate(id){return get('/api/demo/twin/dependents/'+encodeURIComponent(id))}
function render(d){el('rows').replaceChildren();for(const n of d.affected){const tr=document.createElement('tr');for(const value of [n.depth,n.name+' | '+n.node_id,n.state,n.path_node_ids.join(' → ')+' | '+n.path_edge_ids.join(', ')]){const td=document.createElement('td');td.textContent=value;tr.append(td)}el('rows').append(tr)}el('summary').textContent=d.affected.length+' objets (racine incluse) · '+d.impact;el('details').textContent=JSON.stringify({causality:d.causality,redundancy_verified:d.redundancy_verified,excluded_relation_types:d.excluded_relation_types,truncated:d.truncated,live_remediation_authorized:d.live_remediation_authorized},null,2)}
async function action(fn){try{await fn()}catch(e){el('rows').replaceChildren();el('details').textContent='';el('summary').textContent='Erreur : '+e.message}}
el('run').onclick=()=>action(async()=>render(await calculate(el('root').value)));
el('compare').onclick=()=>action(async()=>{const [a,b]=await Promise.all(['ACME-SAN-FABRIC-A','ACME-SAN-FABRIC-B'].map(calculate));render(a);const bs=new Set(b.affected.filter(n=>n.depth>0).map(n=>n.node_id));const common=a.affected.filter(n=>n.depth>0&&bs.has(n.node_id));el('details').textContent+='\nFabric B : '+b.affected.length+' objets. Dépendants communs : '+common.length+'\n'+common.map(n=>n.node_id).join('\n')+'\nChemins alternatifs topologiques seulement, capacité de bascule UNKNOWN.'});
action(async()=>{const g=await get('/api/demo/twin/graph');for(const n of g.nodes){const o=document.createElement('option');o.value=n.node_id;o.textContent=n.name+' | '+n.node_id;el('root').append(o)}if(g.nodes.some(n=>n.node_id==='ACME-SAN-FABRIC-A'))el('root').value='ACME-SAN-FABRIC-A';render(await calculate(el('root').value))});
</script></main></html>"""

