import {jobs,readPlatformSummary,type PlatformSummary,type Result,type Options,type JobStatus} from './index';

// Existing public technical snapshot: no extra permissions, no invented timestamps.
export async function readPocPlatform(options: Options): Promise<Result<PlatformSummary>> {
  if (options.token) return readPlatformSummary(options);
  const unknown = (reason:string): Result<PlatformSummary> => ({
    mode:'PLATFORM',source:'prometheus',retrieved_at:null,tenant_acl_qualified:false,
    state:'UNKNOWN',reason,data:null
  });
  try {
    const r = await fetch('/api/mission-control/snapshot',{
      credentials:'omit',cache:'no-store',redirect:'error',signal:options.signal
    });
    if (!r.ok) return unknown('HTTP_'+r.status);
    const d = await r.json();
    if (!d || !Array.isArray(d.services) || d.services.length !== jobs.length ||
        !Array.isArray(d.metrics)) return unknown('INVALID_RESPONSE');
    const items: JobStatus[] = [];
    for (const job of jobs) {
      const matches = d.services.filter((s: any)=>s && s.name===job);
      if (matches.length!==1) return unknown('INVALID_RESPONSE');
      const up = matches[0].up;
      if (up!==null && up!==0 && up!==1) return unknown('INVALID_RESPONSE');
      // Snapshot has a shared metric timestamp, not a per-job timestamp.
      // Do not misrepresent it as per-job evaluation: use a separate projection below.
      items.push({job,status:'UNKNOWN',at:null,reason:'NO_SAMPLES'});
    }
    // v1 PlatformSummary requires per-job evaluation timestamps. Public snapshot
    // cannot meet that contract: return explicit unknown, not fabricated values.
    return unknown('SNAPSHOT_PER_JOB_TIMESTAMP_UNAVAILABLE');
  } catch(e) {
    if(options.signal?.aborted) throw e;
    return unknown('NETWORK_UNAVAILABLE');
  }
}

export type PocSnapshot = {source:'prometheus · snapshot technique'; counts: {UP:number;DOWN:number;UNKNOWN:number}; services:{job:typeof jobs[number];up:0|1|null}[]; evaluated_at:null};
export function projectPocSnapshot(data:unknown): PocSnapshot|null {
  if (!data || typeof data!=='object') return null;
  const services = (data as {services?:unknown}).services;
  if (!Array.isArray(services)||services.length!==jobs.length) return null;
  const rows:PocSnapshot['services']=[];
  for(const job of jobs){
    const match=services.filter(s=>s && s.name===job);
    if(match.length!==1 || ![0,1,null].includes(match[0].up)) return null;
    rows.push({job,up:match[0].up});
  }
  return {source:'prometheus · snapshot technique',services:rows,evaluated_at:null,counts:{
    UP:rows.filter(s=>s.up===1).length,DOWN:rows.filter(s=>s.up===0).length,UNKNOWN:rows.filter(s=>s.up===null).length
  }};
}
