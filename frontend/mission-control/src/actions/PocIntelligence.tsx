import {useState} from "react";

const cases = [
 {id:"payments",title:"Payments — latence",signal:"Latence élevée (fixture)",hypothesis:"Saturation du pool de connexions",checks:["Comparer la latence et le volume","Vérifier les erreurs de connexion","Contrôler les dépendances"],critic:"Hypothèse non confirmée",runbook:["Observer les métriques","Inspecter les dépendances","Soumettre une hypothèse de remédiation"]},
 {id:"storage",title:"Stockage — capacité",signal:"Capacité élevée (fixture)",hypothesis:"Croissance des fichiers temporaires",checks:["Consulter la capacité","Identifier les volumes concernés","Vérifier la rétention"],critic:"Cause racine non attestée",runbook:["Observer le volume","Identifier les fichiers","Demander une validation humaine"]}
] as const;

export function PocIntelligence({mode,links={}}:{mode:"demo"|"operational";links?:Partial<Record<"Temporal"|"n8n"|"GLPI",string>>}) {
 return mode==="demo"?<SyntheticPanel links={links}/>:<p>Diagnostic métier : UNKNOWN — aucun contexte autorisé.</p>;
}
function SyntheticPanel({links}:{links:Partial<Record<"Temporal"|"n8n"|"GLPI",string>>}) {
 const [selected,setSelected]=useState(0);
 const [question,setQuestion]=useState("diagnostic");
 const [answer,setAnswer]=useState(false);
 const [step,setStep]=useState(0);
 const c=cases[selected];
 function safeLink(value:string|undefined){try{const u=new URL(value||"");return ["https:","http:"].includes(u.protocol)&&!u.username&&!u.password&&!u.search&&!u.hash?u.href:null;}catch{return null;}}
 return <section aria-label="Copilot POC synthétique" style={{minWidth:0,overflowWrap:"anywhere",display:"grid",gap:12}}>
 <h2>Copilot et diagnostic — DEMO synthétique</h2><p>Exemples locaux déterministes. Aucune inférence LLM, lecture runtime ou action réelle.</p>
 <label>Scénario <select value={selected} onChange={e=>{setSelected(Number(e.target.value));setAnswer(false);setStep(0);}}>{cases.map((item,i)=><option key={item.id} value={i}>{item.title}</option>)}</select></label>
 <p>{c.signal}</p>
 <label>Question Copilot <select value={question} onChange={e=>{setQuestion(e.target.value);setAnswer(false);}}><option value="diagnostic">Quelle hypothèse ?</option><option value="checks">Quels contrôles ?</option><option value="risk">Puis-je intervenir ?</option></select></label>
 <button style={{minHeight:44}} type="button" onClick={()=>setAnswer(true)}>Consulter la réponse synthétique</button>
 <div role="status">{answer&&(question==="diagnostic"?c.hypothesis:question==="checks"?c.checks.join(" · "):"Non : HOLD_FOR_HUMAN_REVIEW / DENY_LIVE_ACTION")}</div>
 <h3>Analyste / Critic</h3><p>{c.hypothesis} — {c.critic}. Policy : DENY_LIVE_ACTION.</p>
 <h3>Runbook interactif — répétition locale</h3><ol>{c.runbook.map((item,i)=><li key={item}>{item} — {i<step?"Parcouru localement":"À parcourir"}</li>)}</ol>
 <div style={{display:"flex",flexWrap:"wrap",gap:8}}><button type="button" disabled={step===c.runbook.length} onClick={()=>setStep(s=>Math.min(s+1,c.runbook.length))}>Avancer la répétition locale</button><button type="button" onClick={()=>setStep(0)}>Réinitialiser</button></div>
 <h3>Evidence</h3><p>Progression locale : {step}/{c.runbook.length}. Preuve runtime : MISSING. Rétablissement réel : UNKNOWN. Aucun reçu de simulation serveur créé par ce panneau.</p>
 <h3>Interfaces externes</h3>{(["Temporal","n8n","GLPI"] as const).map(name=>{const url=safeLink(links[name]);return <p key={name}>{name} — {url?<a href={url} target="_blank" rel="noopener noreferrer">Ouvrir interface configurée</a>:"Lien non configuré"} · intégration UNKNOWN</p>;})}
 </section>;
}
