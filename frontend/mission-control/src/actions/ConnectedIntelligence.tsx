import {useEffect,useMemo,useState} from "react";
import {ContextActions} from "./ContextActions";
import {demoProvider} from "./providers";
type Journey={schema:string;mode:string;incident_id:string;run_id:string;source_sha256:string;affected_ci_ids:string[];runtime_attested:boolean;live_remediation_authorized:boolean};
export function ConnectedIntelligence({viewerToken,mode}:{viewerToken:string;mode:"demo"|"operational"}) {
 return mode==="demo"&&viewerToken?<Connected key={viewerToken} viewerToken={viewerToken}/>:<p>Intelligence connectée : UNKNOWN — accès DEMO viewer requis.</p>;
}
function Connected({viewerToken}:{viewerToken:string}) {
 const [journey,setJourney]=useState<Journey|null>(null),[error,setError]=useState(""),[asset,setAsset]=useState(""),[revision,setRevision]=useState(0);
 const provider=useMemo(()=>demoProvider(viewerToken),[viewerToken]);
 useEffect(()=>{
  const controller=new AbortController();setJourney(null);setAsset("");setError("");
  void (async()=>{try{
   const r=await fetch("/api/mission-actions/journey",{headers:{Authorization:"Bearer "+viewerToken},credentials:"omit",cache:"no-store",redirect:"error",signal:controller.signal});
   if(!r.ok)throw Error("Lecture non autorisée ou indisponible");
   const j:Journey=await r.json();
   if(j.schema!=="aiops.mission-actions.journey.v1"||j.mode!=="DEMO"||j.runtime_attested!==false||j.live_remediation_authorized!==false||typeof j.incident_id!=="string"||!j.incident_id||typeof j.run_id!=="string"||!j.run_id||!/^[a-f0-9]{64}$/.test(j.source_sha256)||!Array.isArray(j.affected_ci_ids)||!j.affected_ci_ids.every(x=>typeof x==="string"&&x))throw Error("Contexte non qualifié");
   if(!controller.signal.aborted){setJourney(j);setAsset(j.affected_ci_ids.includes("brocade-fc01")?"brocade-fc01":j.affected_ci_ids[0]||"");}
  }catch{if(!controller.signal.aborted)setError("UNKNOWN — lecture du parcours non qualifiée ou indisponible");}})();
  return ()=>controller.abort();
 },[viewerToken,revision]);
 return <section aria-label="Intelligence connectée DEMO" style={{minWidth:0,overflowWrap:"anywhere"}}>
 <h2>Intelligence connectée au Portal</h2><p>Lecture API authentifiée de références DEMO synthétiques. Aucune inférence LLM ou exécution réelle attestée.</p>
 <button type="button" onClick={()=>{setJourney(null);setAsset("");setRevision(n=>n+1);}}>Actualiser le contexte</button>
 {!journey?<p role="status">{error||"Chargement du parcours…"}</p>:<div key={journey.source_sha256}>
 <p>Incident : {journey.incident_id} · Run : {journey.run_id}</p>
 <h3>Analyste</h3><ContextActions provider={provider} selection={{view:"analysis",id:journey.run_id,runId:journey.run_id,sourceSha256:journey.source_sha256}}/>
 <h3>Critic</h3><ContextActions provider={provider} selection={{view:"critic",id:journey.run_id,runId:journey.run_id,sourceSha256:journey.source_sha256}}/>
 <h3>Policy</h3><ContextActions provider={provider} selection={{view:"policy",id:journey.run_id,runId:journey.run_id,sourceSha256:journey.source_sha256}}/>
 <h3>Références RAG</h3><label>CI <select value={asset} onChange={e=>setAsset(e.target.value)}>{journey.affected_ci_ids.map(id=><option key={id}>{id}</option>)}</select></label>
 {asset&&<ContextActions key={asset} provider={provider} selection={{view:"ci",id:asset,runId:journey.run_id,sourceSha256:journey.source_sha256}}/>}
 <h3>Evidence</h3><ContextActions provider={provider} selection={{view:"evidence",id:journey.run_id,runId:journey.run_id,sourceSha256:journey.source_sha256}}/>
 <p>Temporal / GLPI / n8n : intégration runtime UNKNOWN. Rétablissement réel UNKNOWN.</p>
 </div>}
 </section>;
}
