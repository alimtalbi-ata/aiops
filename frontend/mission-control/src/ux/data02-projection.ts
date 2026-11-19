// DATA02 isolated projection candidate. Not wired into runtime or public barrel.
export type Mode = 'PLATFORM' | 'DEMO' | 'OPERATIONAL';
export type Provenance = {
 origin: 'SYNTHETIC'|'OBSERVED'|'UNKNOWN';
 domain: 'PLATFORM_TECHNICAL'|'PLATFORM_AGGREGATE'|'BUSINESS'|'UNKNOWN';
 source: string; source_sha256: string|null;
 observed_at: number|null; evaluated_at: number|null; retrieved_at: number|null;
 freshness: 'FRESH'|'STALE'|'UNKNOWN';
 tenant_acl_qualified: boolean; runtime_attested: boolean;
};
export type Coverage = {observed:number;expected:number;ratio:number};
export type View = {schema:'aiops.mission-data.view.v2';mode:Mode;provenance:Provenance;coverage:Coverage|null} &
 ({state:'AVAILABLE';data:number;reason:null}|{state:'UNKNOWN';data:null;reason:string});
export type Projection = {value:number|null;reason:string|null;freshness:'UNKNOWN';source:string;coverage:Coverage|null};
export function projectMetric(v:View, mode:'operational'|'demo'):Projection {
 const p=v.provenance;
 const base={value:null,reason:null,freshness:'UNKNOWN' as const,source:p?.source||'UNKNOWN',coverage:null};
 const deny=(reason:string):Projection=>({...base,reason});
 if(v.schema!=='aiops.mission-data.view.v2'||!p||!p.source)return deny('PROVENANCE_UNKNOWN');
 if(mode==='operational'&&(v.mode==='DEMO'||p.origin==='SYNTHETIC'))return deny('MODE_MISMATCH');
 if(mode==='demo'&&(v.mode!=='DEMO'||p.origin!=='SYNTHETIC'))return deny('MODE_MISMATCH');
 if(p.origin==='UNKNOWN'||p.domain==='UNKNOWN')return deny('PROVENANCE_UNKNOWN');
 if(v.state==='UNKNOWN')return deny(v.reason||'UNKNOWN');
 if(mode==='operational'&&p.domain==='PLATFORM_AGGREGATE')return deny('AGGREGATE_AUTHORIZATION_NOT_QUALIFIED');
 if(mode==='operational'&&p.domain==='BUSINESS'&&(v.mode!=='OPERATIONAL'||p.origin!=='OBSERVED'||p.tenant_acl_qualified!==true))return deny('TENANT_ACL_NOT_QUALIFIED');
 if(mode==='operational'&&p.domain==='PLATFORM_TECHNICAL'&&v.mode!=='PLATFORM')return deny('MODE_MISMATCH');
 if(mode==='demo'&&p.runtime_attested!==false)return deny('PROVENANCE_UNKNOWN');
 const c=v.coverage;
 if(c!==null&&(!c||!Number.isSafeInteger(c.observed)||!Number.isSafeInteger(c.expected)||c.expected<=0||c.observed<0||c.observed>c.expected||Math.abs(c.ratio-c.observed/c.expected)>1e-12||!Number.isFinite(c.ratio)))return deny('INVALID_COVERAGE');
 if(!Number.isFinite(v.data))return deny('UNKNOWN');
 return {...base,value:v.data,coverage:c};
}
// V1 is left untouched; no invented v2 provenance.
export function projectLegacyMetric(value:number|null, source:string):Projection {
 return {value:null,reason:'V2_PROVENANCE_UNKNOWN',source:source||'UNKNOWN',freshness:'UNKNOWN',coverage:null};
}
