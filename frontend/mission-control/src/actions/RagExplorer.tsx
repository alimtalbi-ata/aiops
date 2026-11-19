import {useEffect,useState} from "react";
import {qualifiedCitations,searchCitations,type RagCitation} from "./ragContract";
export function RagExplorer({viewerToken,asset}:{viewerToken:string;asset:string}){
 return <Explorer key={JSON.stringify([viewerToken,asset])} viewerToken={viewerToken} asset={asset}/>;
}
function Explorer({viewerToken,asset}:{viewerToken:string;asset:string}){
 const [rows,setRows]=useState<RagCitation[]|null>(null),[status,setStatus]=useState("UNKNOWN"),[query,setQuery]=useState("");
 useEffect(()=>{if(!viewerToken||!asset)return;const c=new AbortController();setStatus("Chargement");
 void (async()=>{try{const r=await fetch("/api/mission-actions/rag?asset="+encodeURIComponent(asset),{headers:{Authorization:"Bearer "+viewerToken},credentials:"omit",cache:"no-store",redirect:"error",signal:c.signal});const data=r.ok?qualifiedCitations(await r.json(),asset):null;if(!c.signal.aborted){setRows(data);setStatus(data?"Références synthétiques disponibles":"UNKNOWN — aucune référence qualifiée");}}catch{if(!c.signal.aborted)setStatus("UNKNOWN — lecture indisponible");}})();return()=>c.abort();},[viewerToken,asset]);
 const matches=searchCitations(rows??[],query);
 return <section aria-label="Recherche RAG connectée" style={{overflowWrap:"anywhere",minWidth:0}}><h3>Recherche RAG — catalogue synthétique connecté</h3><p>Recherche textuelle déterministe, aucune inférence LLM.</p><p role="status">{status}</p><label>Filtrer les références <input value={query} onChange={e=>setQuery(e.target.value)} /></label>{rows&&<p>{matches.length} référence(s) correspondante(s)</p>}{matches.map(c=><article key={c.doc_id}><h4>{c.doc_id}</h4><p>{c.event_key} · {c.sample}</p><ol>{c.runbook.map((s,i)=><li key={i}>{s}</li>)}</ol><details><summary>Empreinte de la référence</summary><code>{c.doc_sha256}</code></details></article>)}</section>;
}
