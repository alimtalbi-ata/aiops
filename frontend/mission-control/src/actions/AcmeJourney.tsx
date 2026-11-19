import {useEffect,useMemo,useState} from "react";
import {ContextActions} from "./ContextActions";
import {demoProvider} from "./providers";
import type {View,Selection} from "./context";

type Journey = {incident_id:string;run_id:string;scenario_id:string;affected_ci_ids:string[];source_sha256:string};
const stages: {view:View;label:string}[]=[
 {view:"incident",label:"Incident"},{view:"ci",label:"Digital Twin"},{view:"scenario",label:"Scénario"},
 {view:"analysis",label:"Analyste"},{view:"critic",label:"Critic"},{view:"policy",label:"Policy"},
 {view:"hitl",label:"HITL"},{view:"execution",label:"Simulation / avant-après"},
 {view:"evidence",label:"Evidence"},{view:"itsm",label:"ITSM / GLPI"}
];
/** Embed inside Team A's graphical workspace. Credentials are supplied by its memory-only session. */
export function AcmeJourney({viewerToken,operatorToken}:{viewerToken:string;operatorToken?:string}) {
 const [qualified,setQualified]=useState<{viewer:string;operator:string}|null>(null);
 const operatorReady=Boolean(operatorToken && qualified?.viewer===viewerToken && qualified?.operator===operatorToken);
 useEffect(()=>{
   const controller=new AbortController();
   setQualified(null);
   if(!viewerToken || !operatorToken)return;
   void (async()=>{
     try{
       const r=await fetch("/api/mission-actions/session/operator",{signal:controller.signal,cache:"no-store",
         credentials:"omit",redirect:"error",headers:{Authorization:"Bearer "+operatorToken}});
       const d=await r.json();
       if(!controller.signal.aborted && r.ok && d.schema==="aiops.mission-actions.operator-session.v1" &&
          d.mode==="DEMO" && d.simulation_authorized===true && d.tenant_acl_qualified===false &&
          d.runtime_attested===false && d.live_remediation_authorized===false)
         setQualified({viewer:viewerToken,operator:operatorToken});
     }catch{/* remain denied */}
   })();
   return()=>controller.abort();
 },[viewerToken,operatorToken]);
 const provider=useMemo(()=>demoProvider(viewerToken,operatorReady?operatorToken:undefined),[viewerToken,operatorToken,operatorReady]);
 const [loaded,setLoaded]=useState<{provider:typeof provider;data:Journey}|null>(null);
 const [chosen,setChosen]=useState(false),[view,setView]=useState<View>("incident"),[ci,setCI]=useState("");
 const [error,setError]=useState("");
 const j=loaded?.provider===provider?loaded.data:null;
 useEffect(()=>{
   const controller=new AbortController();
   setChosen(false);setView("incident");setCI("");setError("");setLoaded(null);
   if(!viewerToken){setError("Session viewer requise");return;}
   void (async()=>{
     try{
       const r=await fetch("/api/mission-actions/journey",{signal:controller.signal,cache:"no-store",
         credentials:"omit",redirect:"error",headers:{Authorization:"Bearer "+viewerToken}});
       const d=await r.json();
       if(!r.ok || d.schema!=="aiops.mission-actions.journey.v1" || d.mode!=="DEMO" ||
         d.runtime_attested!==false || d.live_remediation_authorized!==false ||
         ![d.incident_id,d.run_id,d.scenario_id,d.source_sha256].every(x=>typeof x==="string"&&x.length>0) ||
         !Array.isArray(d.affected_ci_ids) || !d.affected_ci_ids.every((x:unknown)=>typeof x==="string"))
         throw Error("Parcours non qualifié");
       if(!controller.signal.aborted){setLoaded({provider,data:d});setCI(d.affected_ci_ids[0]??"");}
     }catch{if(!controller.signal.aborted)setError("Parcours indisponible ou non autorisé");}
   })();
   return()=>controller.abort();
 },[provider,viewerToken]);
 const selection:Selection|undefined=j&&chosen?{view,runId:j.run_id,sourceSha256:j.source_sha256,id:view==="incident"?j.incident_id:view==="ci"?ci:view==="scenario"?j.scenario_id:j.run_id}:undefined;
 return <section className="panel" aria-label="Parcours ACME synthétique">
   <h2>ACME · parcours DEMO isolé</h2>
   <p>Aucune preuve runtime, approbation réelle ou écriture GLPI.</p>
   <p role="status">Opérateur DEMO : {operatorReady?"Autorisation vérifiée":"Non qualifié — simulation désactivée"}</p>
   {!j?<p role="status">{error||"Chargement…"}</p>:<>
     <label>Incident <select value={chosen?j.incident_id:""} onChange={e=>setChosen(e.target.value===j.incident_id)}>
       <option value="">Sélectionner un incident</option><option value={j.incident_id}>{j.incident_id}</option>
     </select></label>
     {chosen&&<><p>Run synthétique : {j.run_id}</p>
       <nav aria-label="Étapes ACME">{stages.map(s=><button type="button" key={s.view} aria-pressed={view===s.view} onClick={()=>setView(s.view)}>{s.label}</button>)}</nav>
       {view==="ci"&&<label>CI <select value={ci} onChange={e=>setCI(e.target.value)}>{j.affected_ci_ids.map(id=><option key={id}>{id}</option>)}</select></label>}
       {selection&&<ContextActions provider={provider} selection={selection}/>}
     </>}
   </>}
 </section>;
}
