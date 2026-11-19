import {loadPocTechnical} from './poc-technical';
import {jobs} from './index';
async function main(){
 const calls:string[]=[];
 const original=globalThis.fetch;
 const check=(ok:boolean)=>{if(!ok)throw Error('POC02 assertion failed');};
 globalThis.fetch=async (input,init)=>{
   const path=String(input);calls.push(path);
   check(!init?.method||init.method==='GET');
   if(path==='/api/mission-control/snapshot'){
     check(!init?.headers);
     return new Response(JSON.stringify({services:jobs.map((name,i)=>({name,up:i===0?0:i===1?null:1}))}),{status:200});
   }
   check((init?.headers as Record<string,string>).Authorization==='Bearer fixture-only');
   return new Response('{}',{status:401});
 };
 try {
   const a=await loadPocTechnical({token:''});
   check(calls.length===1);
   check(a.snapshot?.counts.UP===4&&a.snapshot.counts.DOWN===1&&a.snapshot.counts.UNKNOWN===1);
   check(a.availability.state==='UNKNOWN'&&a.availability.reason==='VIEWER_REQUIRED');
   check(a.kpis.every(k=>k.value===null&&k.reason==='VIEWER_REQUIRED'));
   const b=await loadPocTechnical({token:'fixture-only'});
   check(calls.length===11);
   check(b.snapshot?.counts.DOWN===1);
   check(b.platform.state==='UNKNOWN'&&b.platform.reason==='HTTP_401');
   check(b.kpis.every(k=>k.value===null&&k.reason==='HTTP_401'));
   console.log('POC02 mock checks PASS');
 } finally {globalThis.fetch=original;}
}
void main();
