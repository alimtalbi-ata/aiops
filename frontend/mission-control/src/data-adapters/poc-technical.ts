import {readPocSnapshot,type PocSnapshot} from './poc-platform';
import {readPlatformSummary,readAvailabilityHistory,readTechnicalHistory,readAggregateKpis,aggregateValue,type Options,type Result,type PlatformSummary,type AvailabilityHistory,type TechnicalHistory,type AggregateHistory} from './index';

export type PocTechnical = {
  snapshot: PocSnapshot|null;
  platform: Result<PlatformSummary>;
  availability: Result<AvailabilityHistory>;
  technical: Result<TechnicalHistory>[];
  aggregateHistory?: {core:Result<AggregateHistory<'core'>>;evidence:Result<AggregateHistory<'evidence'>>;twin:Result<AggregateHistory<'twin'>>;fs:Result<AggregateHistory<'fs-lab'>>;services:Result<AggregateHistory<'services'>>};
  kpis: {id:string;label:string;value:number|null;unit:string;source:string;kind:'technical';reason:string|null}[];
};
const denied = <T>():Result<T> => ({mode:'PLATFORM',source:'prometheus',retrieved_at:null,tenant_acl_qualified:false,state:'UNKNOWN',reason:'VIEWER_REQUIRED',data:null});
// Token supplied in memory by caller; no persistence or new endpoint.
export async function loadPocTechnical(options:Options, minutes=60):Promise<PocTechnical>{
  const snapshotPromise=readPocSnapshot({signal:options.signal});
  const authorized=!!options.token;
  const [snapshot,platform,availability,duration,samples,core,evidence,twin,fs,sv]=await Promise.all([
    snapshotPromise,
    authorized?readPlatformSummary(options):denied<PlatformSummary>(),
    authorized?readAvailabilityHistory(options,minutes):denied<AvailabilityHistory>(),
    authorized?readTechnicalHistory('scrape-duration',options,minutes):denied<TechnicalHistory>(),
    authorized?readTechnicalHistory('scrape-samples',options,minutes):denied<TechnicalHistory>(),
    authorized?readAggregateKpis('core',options,minutes):null,
    authorized?readAggregateKpis('evidence',options,minutes):null,
    authorized?readAggregateKpis('twin',options,minutes):null,
    authorized?readAggregateKpis('fs-lab',options,minutes):null,
    authorized?readAggregateKpis('services',options,minutes):null
  ]);
  const kpi=(id:string,label:string,value:number|null,unit:string,r:{state:string;reason:string|null}|null)=>({
    id,label,value,unit,source:'Prometheus · agrégats non partitionnés',kind:'technical' as const,
    reason:value!==null?null:r===null?'VIEWER_REQUIRED':r.reason??'NO_CURRENT_SAMPLE'
  });
  return {snapshot,platform,availability,technical:[duration,samples],aggregateHistory:{core:core??denied<AggregateHistory<'core'>>(),evidence:evidence??denied<AggregateHistory<'evidence'>>(),twin:twin??denied<AggregateHistory<'twin'>>(),fs:fs??denied<AggregateHistory<'fs-lab'>>(),services:sv??denied<AggregateHistory<'services'>>()},kpis:[
    kpi('runs','Runs',core?aggregateValue(core,'aiops_runs_total'):null,'count',core),
    kpi('running','En cours',core?aggregateValue(core,'aiops_runs_running'):null,'count',core),
    kpi('blocked','Bloqués',core?aggregateValue(core,'aiops_runs_blocked'):null,'count',core),
    kpi('resolved','Résolus',core?aggregateValue(core,'aiops_runs_resolved'):null,'count',core),
    kpi('evidence','Evidence',evidence?aggregateValue(evidence,'aiops_evidence_total'):null,'count',evidence),
    kpi('nodes','CI Twin',twin?aggregateValue(twin,'aiops_twin_nodes'):null,'count',twin),
    kpi('degraded','CI dégradés',twin?aggregateValue(twin,'aiops_twin_degraded'):null,'count',twin),
    kpi('failed','CI en échec',twin?aggregateValue(twin,'aiops_twin_failed'):null,'count',twin),
    kpi('fs','FS LAB',fs?aggregateValue(fs,'aiops2_fs_lab_used_percent'):null,'%',fs),
    kpi('alert','Alerte FS LAB',fs?aggregateValue(fs,'aiops2_fs_lab_alert_firing'):null,'binary',fs),
    kpi('worker','Worker',sv?aggregateValue(sv,'aiops_worker_up'):null,'binary',sv),
    kpi('policy','Policy',sv?aggregateValue(sv,'aiops_policy_up'):null,'binary',sv),
    kpi('portal','Portal',sv?aggregateValue(sv,'aiops_portal_up'):null,'binary',sv)
  ]};
}
