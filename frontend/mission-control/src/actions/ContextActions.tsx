import { useEffect, useRef, useState } from "react";
import { commands, labels, type ActionProvider, type Command, type Reply, type Selection } from "./context";

/** Inline slot for existing graphical cards/drawers; no portal, token input or links. */
export function ContextActions({provider,selection}:{provider:ActionProvider;selection:Selection}) {
  const key=JSON.stringify([provider.mode,selection.view,selection.id,selection.runId,selection.sourceSha256]);
  const pending=useRef<AbortController|null>(null);
  const [reply,setReply]=useState<{key:string;provider:ActionProvider;value:Reply}|null>(null);
  const [busy,setBusy]=useState(false);
  useEffect(()=>{setReply(null);setBusy(false);return()=>{pending.current?.abort();pending.current=null;};},[provider,key]);
  async function invoke(command:Command) {
    if(pending.current) return;
    const controller=new AbortController();pending.current=controller;setBusy(true);setReply(null);
    try {
      const value=await provider.invoke(selection,command,controller.signal);
      if(!controller.signal.aborted) setReply({key,provider,value});
    } catch {
      if(!controller.signal.aborted) setReply({key,provider,value:{state:"UNKNOWN",detail:{reason:"NETWORK_OR_RESPONSE_ERROR"}}});
    } finally {
      if(pending.current===controller){pending.current=null;setBusy(false);}
    }
  }
  const visible=reply?.key===key && reply.provider===provider?reply.value:null;
  return <div className="mission-context-actions" aria-label={"Actions "+selection.view}>
    <small>{provider.mode==="DEMO"?"DEMO · simulation uniquement":"OPÉRATIONNEL · autorité requise"}</small>
    <div>{commands[selection.view].map(command=><button type="button" key={command}
      disabled={busy || !selection.id || ["approve","reject"].includes(command) || (command==="execute" && !provider.canSimulate) ||
        (provider.mode==="OPERATIONAL" && (selection.view!=="run" || command!=="inspect"))}
      onClick={()=>void invoke(command)}>{labels[command]}</button>)}</div>
    <p role="status">{busy?"Interrogation…":visible?visible.state:"Aucune réponse métier"}</p>
    {visible && <details open><summary>Résultat et provenance {visible.http? "· HTTP "+visible.http:""}</summary>
      <StructuredResult detail={visible.detail}/></details>}
  </div>;
}

function StructuredResult({detail}:{detail:unknown}) {
  if (detail==null) return <p>Indisponible</p>;
  if (Array.isArray(detail)) return <ul>{detail.map((item,i)=><li key={i}><StructuredResult detail={item}/></li>)}</ul>;
  if (typeof detail!=="object") return <span>{typeof detail==="boolean"?(detail?"Oui":"Non"):String(detail)}</span>;
  const d=detail as Record<string,unknown>;
  if (Array.isArray(d.timeline) && typeof d.cursor==="number") {
    const cursor=d.cursor;
    return <section aria-label="Progression du scénario">
      <p>Checkpoint {cursor+1} / {d.timeline.length} · simulation</p>
      <progress value={cursor+1} max={d.timeline.length}/>
      <ol>{d.timeline.map((item,i)=><li key={i} aria-current={i===cursor?"step":undefined}>
        <StructuredResult detail={item}/></li>)}</ol>
      <p>Preuves runtime : absentes</p><small>Source : {String(d.source_sha256)}</small>
    </section>;
  }
  if (d.schema==="aiops.acme-demo-simulation-pipeline.v1") {
    const sim=d.simulation as Record<string,unknown>|undefined;
    const receipt=sim?.receipt as Record<string,unknown>|undefined;
    return <section aria-label="Résultat de simulation">
      <h4>Effet hypothétique — aucune action réelle</h4>
      <div className="drawer-kpis"><div>Avant <StructuredResult detail={receipt?.before}/></div>
      <div>Après hypothétique <StructuredResult detail={receipt?.hypothetical_after}/></div></div>
      <p>Rétablissement réel : inconnu · Temporal : non exécuté</p>
      <h4>Reçu synthétique</h4><code style={{overflowWrap:"anywhere"}}>{String(sim?.receipt_sha256??"Absent")}</code>
      <h4>Qualification des preuves</h4><StructuredResult detail={d.evidence_gate}/>
    </section>;
  }
  return <dl>{Object.entries(d).map(([key,value])=><div key={key} style={{marginBlock:6}}>
    <dt style={{fontWeight:600}}>{key.replace(/_/g," ")}</dt>
    <dd style={{marginInlineStart:12,overflowWrap:"anywhere"}}><StructuredResult detail={value}/></dd></div>)}</dl>;
}
