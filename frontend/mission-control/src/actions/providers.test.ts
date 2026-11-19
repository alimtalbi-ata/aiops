import {demoProvider} from "./providers";

/** Dependency-free contract checks; invoke from a test runner with fetch/Response support. */
export async function verifyProviderContracts() {
 const original=globalThis.fetch;
 const calls:string[]=[];
 const journey={schema:"aiops.mission-actions.journey.v1",mode:"DEMO",runtime_attested:false,live_remediation_authorized:false,source_sha256:"a".repeat(64),run_id:"SIM-1",incident_id:"I",scenario_id:"S"};
 try {
   globalThis.fetch=async (input)=>{
     const path=String(input);calls.push(path);
     return new Response(JSON.stringify(path.endsWith("/journey")?journey:{detail:"denied"}),{status:path.endsWith("/journey")?200:401});
   };
   const provider=demoProvider("viewer","operator");
   const signal=new AbortController().signal;
   const denied=await provider.invoke({view:"execution",id:"SIM-1",sourceSha256:journey.source_sha256},"execute",signal);
   if(denied.state!=="BLOCKED" || !calls.some(p=>p.endsWith("/session/operator")) || calls.some(p=>p.endsWith("/demo/simulation")))throw Error("operator gate failed");
   calls.length=0;
   const stale=await provider.invoke({view:"execution",id:"SIM-1",sourceSha256:"b".repeat(64)},"execute",signal);
   if(stale.state!=="BLOCKED" || calls.length!==1)throw Error("fixture fence failed");
 } finally {globalThis.fetch=original;}
}
