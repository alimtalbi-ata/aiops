import { useEffect, useRef, useState } from "react";
import { commands, labels, type ActionProvider, type Command, type Reply, type Selection } from "./context";

/** Inline slot for existing graphical cards/drawers; no portal, token input or links. */
export function ContextActions({provider,selection}:{provider:ActionProvider;selection:Selection}) {
  const key=JSON.stringify([provider.mode,selection.view,selection.id,selection.runId]);
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
      disabled={busy || !selection.id || ["execute","approve","reject"].includes(command) ||
        (provider.mode==="OPERATIONAL" && (selection.view!=="run" || command!=="inspect"))}
      onClick={()=>void invoke(command)}>{labels[command]}</button>)}</div>
    <p role="status">{busy?"Interrogation…":visible?visible.state:"Aucune réponse métier"}</p>
    {visible && <details open><summary>Résultat et provenance {visible.http? "· HTTP "+visible.http:""}</summary>
      <pre style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>{JSON.stringify(visible.detail,null,2)}</pre></details>}
  </div>;
}
