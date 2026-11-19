/**
 * SYNTHETIC fixtures — never claim these events, timestamps or scores are live.
 * UI grouping idea adapted from Aurora's recurrence grouping and evidence-first UX.
 */
export type Health = "healthy" | "degraded" | "critical";
export type Service = { id: string; name: string; namespace: string; health: Health; rpm: number; errors: number; p95: number; calls: string[] };
export type TraceSpan = { name: string; service: string; duration: number; offset: number; status: "ok" | "error"; parent?: string };
export type Trace = { id: string; operation: string; service: string; duration: number; spans: number; timestamp: string; status: "ok" | "error"; details: TraceSpan[] };
export type Evidence = { id: string; label: string; type: "trace" | "log" | "metric" | "change"; observation: string; source: string };
export type Incident = { id: string; title: string; service: string; severity: "critical" | "major" | "minor"; status: "investigating" | "analyzed" | "resolved"; recurrenceOf?: string; firedAt: string; count?: number; summary: string; evidence: Evidence[] };

export const services: Service[] = [
  {id:"gateway",name:"api-gateway",namespace:"production",health:"healthy",rpm:1275,errors:0.3,p95:89,calls:["checkout","catalog","auth"]},
  {id:"checkout",name:"checkout-service",namespace:"production",health:"degraded",rpm:811,errors:3.8,p95:840,calls:["payment","inventory"]},
  {id:"payment",name:"payment-service",namespace:"production",health:"critical",rpm:493,errors:8.1,p95:1742,calls:["postgres"]},
  {id:"catalog",name:"product-catalog",namespace:"production",health:"healthy",rpm:2134,errors:0.1,p95:72,calls:["postgres"]},
  {id:"auth",name:"auth-service",namespace:"production",health:"healthy",rpm:765,errors:0.2,p95:98,calls:[]},
  {id:"inventory",name:"inventory-service",namespace:"production",health:"healthy",rpm:321,errors:0.5,p95:118,calls:["postgres"]},
  {id:"postgres",name:"postgresql",namespace:"database",health:"degraded",rpm:3542,errors:1.1,p95:383,calls:[]}
];

export const traces: Trace[] = [
  {id:"b743e0a9271e4c9b",operation:"POST /api/checkout",service:"checkout-service",duration:2413,spans:8,timestamp:"2026-11-09 14:32:08",status:"error",
   details:[{name:"POST /api/checkout",service:"checkout-service",duration:2413,offset:0,status:"error"},
    {name:"inventory.reserve",service:"inventory-service",duration:193,offset:84,status:"ok",parent:"checkout"},
    {name:"payments.authorize",service:"payment-service",duration:1902,offset:287,status:"error",parent:"checkout"},
    {name:"db.query",service:"postgresql",duration:1456,offset:356,status:"error",parent:"payments"}]},
  {id:"ac9e713dd108436e",operation:"GET /api/products",service:"api-gateway",duration:86,spans:4,timestamp:"2026-11-09 14:31:50",status:"ok",
   details:[{name:"GET /api/products",service:"api-gateway",duration:86,offset:0,status:"ok"},{name:"catalog.list",service:"product-catalog",duration:52,offset:16,status:"ok",parent:"gateway"}]},
  {id:"79bdef108a5e47aa",operation:"POST /api/payments",service:"payment-service",duration:1754,spans:6,timestamp:"2026-11-09 14:31:12",status:"error",
   details:[{name:"POST /api/payments",service:"payment-service",duration:1754,offset:0,status:"error"},{name:"db.acquire",service:"postgresql",duration:1490,offset:80,status:"error",parent:"payments"}]},
  {id:"af1beac40e988199",operation:"GET /api/session",service:"auth-service",duration:91,spans:3,timestamp:"2026-11-09 14:30:09",status:"ok",
   details:[{name:"GET /api/session",service:"auth-service",duration:91,offset:0,status:"ok"}]}
];

export const incidents: Incident[] = [
  {id:"INC-2048",title:"Échecs de paiement — saturation du pool de connexions",service:"payment-service",severity:"critical",status:"investigating",firedAt:"2026-11-09T14:32:00Z",count:3,summary:"Hypothèse en cours : saturation des connexions PostgreSQL. Aucune cause racine confirmée.",evidence:[
    {id:"E1",label:"Trace lente",type:"trace",source:"b743e0a9271e4c9b",observation:"payments.authorize a duré 1 902 ms"},
    {id:"E2",label:"Latence P95",type:"metric",source:"payment-service:p95",observation:"P95 synthétique : 1 742 ms"},
    {id:"E3",label:"Pool DB",type:"log",source:"demo-log-connection-pool",observation:"Exemple : délai d'acquisition d'une connexion"}]},
  {id:"INC-2049",title:"Récurrence de l’alerte payment-timeout",service:"payment-service",severity:"major",status:"investigating",recurrenceOf:"INC-2048",firedAt:"2026-11-09T14:35:00Z",summary:"Alerte rattachée à l’incident principal.",evidence:[]},
  {id:"INC-2050",title:"Nouvelle récurrence payment-timeout",service:"payment-service",severity:"major",status:"investigating",recurrenceOf:"INC-2048",firedAt:"2026-11-09T14:37:00Z",summary:"Alerte rattachée à l’incident principal.",evidence:[]},
  {id:"INC-2047",title:"Dérive de latence sur checkout-service",service:"checkout-service",severity:"major",status:"analyzed",firedAt:"2026-11-09T13:04:00Z",summary:"Corrélation temporelle avec les appels de paiement. Le mécanisme précis reste non vérifié.",evidence:[
    {id:"E4",label:"Trace checkout",type:"trace",source:"b743e0a9271e4c9b",observation:"Le chemin checkout → payment présente la latence la plus élevée"}]}
];

export type IncidentGroup = { anchor: Incident; occurrences: Incident[]; lastFire: number };
export function groupIncidents(rows: Incident[]): IncidentGroup[] {
  // Adapted from Aurora recurrence grouping; orphan incidents remain visible.
  const byId = new Map(rows.map(i=>[i.id,i]));
  const members = new Map<string,Incident[]>();
  const anchors: Incident[] = [];
  for (const item of rows) {
    const parent = item.recurrenceOf ? byId.get(item.recurrenceOf) : undefined;
    if (parent && !parent.recurrenceOf) members.set(parent.id,[...(members.get(parent.id)||[]),item]);
    else anchors.push(item);
  }
  return anchors.map(anchor=>{
    const occurrences=[anchor,...(members.get(anchor.id)||[])].sort((a,b)=>Date.parse(a.firedAt)-Date.parse(b.firedAt));
    return {anchor,occurrences,lastFire:Math.max(...occurrences.map(i=>Date.parse(i.firedAt)))};
  }).sort((a,b)=>b.lastFire-a.lastFire);
}
