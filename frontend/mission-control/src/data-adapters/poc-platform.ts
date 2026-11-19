import {jobs,type Options} from './index';

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

export async function readPocSnapshot(options: Pick<Options,'signal'> = {}): Promise<PocSnapshot|null> {
  try {
    const r = await fetch('/api/mission-control/snapshot',{credentials:'omit',cache:'no-store',redirect:'error',signal:options.signal});
    return r.ok ? projectPocSnapshot(await r.json()) : null;
  } catch(e) { if(options.signal?.aborted) throw e; return null; }
}
