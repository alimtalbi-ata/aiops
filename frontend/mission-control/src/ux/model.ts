export type Health = 'healthy' | 'degraded' | 'critical';
export interface TwinService { id:string; name:string; health:Health; rpm:number; p95:number; errors:number; calls:string[]; }
export const demoServices: TwinService[] = [
{id:'gateway',name:'API Gateway',health:'healthy',rpm:4200,p95:110,errors:0.2,calls:['checkout','catalog','auth']},
{id:'checkout',name:'Checkout',health:'degraded',rpm:1200,p95:480,errors:2.4,calls:['payment','inventory']},
{id:'catalog',name:'Catalog',health:'healthy',rpm:1900,p95:85,errors:0.1,calls:['inventory']},
{id:'auth',name:'Identity',health:'healthy',rpm:1100,p95:62,errors:0.1,calls:[]},
{id:'payment',name:'Payment',health:'critical',rpm:940,p95:1240,errors:8.2,calls:['postgres']},
{id:'inventory',name:'Inventory',health:'healthy',rpm:760,p95:94,errors:0.3,calls:['postgres']},
{id:'postgres',name:'PostgreSQL',health:'degraded',rpm:1500,p95:310,errors:1.8,calls:[]}
];
// Potential upstream impact, not confirmed causality.
export function upstreamImpact(services: readonly TwinService[], id:string): string[] {
 if (!services.some(s=>s.id===id)) return [];
 const seen=new Set([id]); const queue=[id];
 for(let i=0;i<queue.length;i++) for(const s of services) {
   if(!seen.has(s.id)&&s.calls.includes(queue[i])) {seen.add(s.id);queue.push(s.id);}
 }
 return queue.slice(1);
}
