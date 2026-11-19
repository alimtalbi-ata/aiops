import {useState} from 'react';
import {AvailabilityPanel,TimeSeries} from './OperationalDashboard';
import type {OperationalData,OperationalKpi,ReadResult,Observation} from './operational';
import type {MissionPage} from './contract';
export type PocTechnicalData={
 snapshot?:{source:string;services:readonly {job:string;up:0|1|null}[];evaluated_at:number|null}|null;
 history?:Pick<OperationalData,'availability'|'technical'>;
 aggregateHistory?:Partial<Record<'core'|'evidence'|'twin'|'fs'|'services',ReadResult<{classification:'PLATFORM_AGGREGATES_UNPARTITIONED';series:{metric:string;unit:string;points:Observation[];coverage:number;reason:string|null}[]}>>>;
 kpis?:readonly (OperationalKpi & {reason?:string|null})[];
 links?:Partial<Record<'Grafana'|'Prometheus'|'Loki'|'Tempo',string>>;
 onRefresh?:()=>void;
 loading?:boolean;
};
function safeLink(raw:string|undefined){try{const u=new URL(raw??'');return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password&&!u.search&&!u.hash?u.href:null}catch{return null}}
function utc(at:number|null|undefined){return typeof at==='number'&&Number.isFinite(at)&&Math.abs(at)<=8640000000000?new Date(at*1000).toISOString():'UNKNOWN'}
export function PocTechnical({data,page,navigate}:{data:PocTechnicalData;page:MissionPage;navigate:(p:MissionPage)=>void}){
 const [job,setJob]=useState('');
 const [group,setGroup]=useState<'core'|'evidence'|'twin'|'fs'|'services'>('core');
 const aggregate=data.aggregateHistory?.[group];
 const snapshot=data.snapshot;
 const rows=snapshot?.services??[];
 const technical=(data.history?.technical??[]).filter(r=>r.mode==='PLATFORM');
 const series=technical.flatMap(r=>r.state==='AVAILABLE'?r.data.series.map(s=>({...s,metric:r.data.metric,unit:r.data.unit,source:r.source})):[]);
 const jobs=[...new Set(series.map(s=>s.job))];
 const active=jobs.includes(job)?job:jobs[0];
 const availability=data.history?.availability;
 return <section className="ux-panel ux-poc-technical" aria-label="Plateforme technique réelle">
 <h2>Plateforme technique réelle · lecture seule</h2>
 <p>Observations de la plateforme, distinctes du scénario Commerce synthétique. Santé métier UNKNOWN.</p>
 <div className="ux-row">{(['UP','DOWN','UNKNOWN'] as const).map(state=><div className="ux-metric" key={state}><small>Jobs {state}</small><strong>{snapshot?rows.filter(r=>r.up===(state==='UP'?1:state==='DOWN'?0:null)).length:'UNKNOWN'}</strong></div>)}</div>
 <p>Source : {snapshot?.source??'UNKNOWN'} · Évaluation : {utc(snapshot?.evaluated_at)}</p>
 <div className="ux-row"><button onClick={()=>navigate('Services')}>Services techniques</button><button onClick={()=>navigate('Observabilité')}>Historiques techniques</button>{data.onRefresh&&<button disabled={data.loading} onClick={data.onRefresh}>{data.loading?'Actualisation…':'Actualiser les observations'}</button>}</div>
 {page==='Services'&&<div className="ux-scroll"><table><thead><tr><th>Job technique</th><th>État observé</th></tr></thead><tbody>{rows.map(r=><tr key={r.job}><td>{r.job}</td><td>{r.up===1?'UP':r.up===0?'DOWN':'UNKNOWN'}</td></tr>)}</tbody></table>{!rows.length&&<p>UNKNOWN · snapshot indisponible</p>}</div>}
 {page==='Observabilité'&&<><AvailabilityPanel data={availability?.mode==='PLATFORM'?availability:undefined}/><h3>Collecte technique · maximum par job</h3>{jobs.length?<label>Job technique <select value={active} onChange={e=>setJob(e.target.value)}>{jobs.map(j=><option key={j}>{j}</option>)}</select></label>:<p>UNKNOWN · historiques non fournis</p>}{technical.map((r,i)=>r.state==='UNKNOWN'?<p key={i}>{r.source} · {r.reason}</p>:null)}<div className="ux-grid">{series.filter(s=>s.job===active).map(s=><TimeSeries key={s.metric} label={(s.metric==='scrape-duration'?'Durée de collecte':'Échantillons collectés')+' · '+s.source} unit={s.unit} points={s.points}/>)}</div></>}
 {page==='Observabilité'&&<section aria-label="Historiques des agrégats"><h3>Historiques des agrégats techniques</h3><p>Non partitionnés · aucune qualification métier.</p><label>Groupe agrégé <select value={group} onChange={e=>setGroup(e.target.value as typeof group)}>{(['core','evidence','twin','fs','services'] as const).map(g=><option key={g}>{g}</option>)}</select></label>{aggregate?.state==='AVAILABLE'&&aggregate.mode==='PLATFORM'&&aggregate.data.classification==='PLATFORM_AGGREGATES_UNPARTITIONED'?<div className="ux-grid">{aggregate.data.series.map(s=><div key={s.metric}><TimeSeries points={s.points} label={s.metric+' · '+aggregate.source} unit={s.unit}/><small>Couverture de la fenêtre fournie : {Math.round(s.coverage*100)}% · {s.reason??'Observation disponible'}</small></div>)}</div>:<p>UNKNOWN · {aggregate?.state==='UNKNOWN'?aggregate.reason:'Historique non fourni ou classification incompatible'}</p>}</section>}
 {page==='Vue globale'&&<section aria-label="Agrégats techniques"><h3>Indicateurs techniques complémentaires</h3><p>Prometheus · agrégats non partitionnés, pas de qualification métier.</p><div className="ux-kpis">{(data.kpis??[]).filter(k=>k.kind==='technical').map(k=><div className="ux-metric" key={k.id}><small>{k.label}</small><strong>{typeof k.value==='number'&&Number.isFinite(k.value)?k.value+' '+k.unit:'UNKNOWN'}</strong><small>{k.source}</small>{(k.value===null||!Number.isFinite(k.value))&&<small>{k.reason??'NO_CURRENT_SAMPLE'}</small>}</div>)}</div>{!data.kpis?.some(k=>k.kind==='technical')&&<p>UNKNOWN · agrégats non fournis</p>}</section>}
 <div className="ux-row">{(['Grafana','Prometheus','Loki','Tempo'] as const).map(name=>{const url=safeLink(data.links?.[name]);return url?<a key={name} href={url} target="_blank" rel="noopener noreferrer">{name}</a>:<small key={name}>{name} · lien non configuré</small>})}</div>
 </section>
}
