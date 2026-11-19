// Structural projection of B 13a62e5; no runtime fetch or fixture.
export type Observation={at:number;value:number|null};
export type AvailabilityPoint={at:number;up:0|1|null};
export type AvailabilityHistory={series:{job:string;points:AvailabilityPoint[];observed:number;expected:number;coverage:number;last_evaluated_at:number|null}[];start:number;end:number;step_seconds:60;coverage:number;classification:'PLATFORM_TECHNICAL_ONLY';freshness:'QUERY_EVALUATION_TIME_NOT_SCRAPE_TIME'};
export type TechnicalHistory={metric:'scrape-duration'|'scrape-samples';unit:'seconds'|'samples';series:{job:string;points:Observation[];coverage:number;last_evaluated_at:number|null}[];start:number;end:number;step_seconds:60;aggregation:'MAX_BY_JOB';classification:'PLATFORM_TECHNICAL_ONLY';freshness:'QUERY_EVALUATION_TIME_NOT_SCRAPE_TIME'};
export type ReadResult<T>={source:string;retrieved_at:number|null;mode:string;tenant_acl_qualified:false}&({state:'AVAILABLE';reason:null;data:T}|{state:'UNKNOWN';reason:string;data:null});
export type OperationalKpi={id:string;label:string;value:number|null;unit:string;source:string;kind:'business'|'technical'};
export type IncidentView={incident_id:string;title?:string;severity:string;state?:string;service_id?:string|null;synthetic:boolean};
export type CIView={node_id:string;name:string;type:string;state:string;site?:string|null;health:number|null;confidence?:number|null;criticality?:string|number|null};
export type Comparison={id:string;label:string;unit:string;source:string;before:Observation;after:Observation};
export type OperationalData={availability?:ReadResult<AvailabilityHistory>;technical?:ReadResult<TechnicalHistory>[];kpis?:OperationalKpi[];incidents?:IncidentView[];ci?:CIView[];comparisons?:Comparison[]};
export function availabilityStats(points:AvailabilityPoint[]){
 const observed=points.filter(p=>p.up===0||p.up===1);
 return {observed:observed.length,expected:points.length,coverage:points.length?observed.length/points.length:null,upRatio:observed.length?observed.filter(p=>p.up===1).length/observed.length:null};
}
export function difference(c:Comparison){return c.before.value===null||c.after.value===null||!Number.isFinite(c.before.value)||!Number.isFinite(c.after.value)||c.after.at<=c.before.at?null:c.after.value-c.before.value;}
export function severityRank(s:string){const ranks:Record<string,number>={P1:0,CRITICAL:0,P2:1,HIGH:1,P3:2,MEDIUM:2,P4:3,LOW:3};return ranks[s.toUpperCase()]??4;}
