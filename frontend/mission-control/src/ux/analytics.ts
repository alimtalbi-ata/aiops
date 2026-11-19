import type {TwinService,Health} from './model';

export function topologyLayout(services: readonly TwinService[]) {
 const ids=new Set(services.map(s=>s.id));
 const levels=new Map(services.map(s=>[s.id,0]));
 // Bounded relaxation: cycles cannot cause endless traversal.
 for(let pass=0;pass<services.length-1;pass++){
  let changed=false;
  for(const s of services) for(const target of s.calls) if(ids.has(target)&&target!==s.id){
   const next=Math.min(services.length-1,levels.get(s.id)!+1);
   if(next>levels.get(target)!){levels.set(target,next);changed=true;}
  }
  if(!changed)break;
 }
 const columns=[...new Set(levels.values())].sort((a,b)=>a-b);
 const rows=new Map<number,number>();
 const positions=new Map(services.map(s=>{
  const column=columns.indexOf(levels.get(s.id)!);
  const row=rows.get(column)??0;rows.set(column,row+1);
  return [s.id,{x:30+column*230,y:54+row*112}] as const;
 }));
 return {positions,width:Math.max(460,columns.length*230+30),height:Math.max(300,...[...rows.values()].map(n=>n*112+60))};
}
export type Sample={slot:number;rpm:number;errors:number;p95:number;health:Health};
export function syntheticSeries(service:TwinService,count:number):Sample[]{
 return Array.from({length:Math.max(0,Math.min(48,Math.floor(count)))},(_,i)=>{
  const factor=0.75+((i*7+service.id.length)%11)/20;
  const errors=Number((service.errors*factor).toFixed(2));
  return {slot:i,rpm:Math.round(service.rpm*factor),errors,p95:Math.round(service.p95*factor),health:errors>=5?'critical':errors>=1?'degraded':'healthy'};
 });
}
export function aggregateSeries(services:readonly TwinService[],count:number){
 const series=services.map(s=>syntheticSeries(s,count));
 return Array.from({length:Math.max(0,Math.min(48,Math.floor(count)))},(_,i)=>{
  const rpm=series.reduce((sum,s)=>sum+s[i].rpm,0);
  const errors=rpm?series.reduce((sum,s)=>sum+s[i].rpm*s[i].errors,0)/rpm:0;
  return {slot:i,rpm,errors:Number(errors.toFixed(2))};
 });
}
