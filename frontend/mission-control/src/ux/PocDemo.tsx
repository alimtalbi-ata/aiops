import {useState} from 'react';
import {MissionControl,Panel,Timeline} from './MissionControl';
import {demoServices,upstreamImpact} from './model';
import {syntheticSeries} from './analytics';
import type {MissionControlProps,MissionPage} from './contract';
import './poc-demo.css';

const history=Object.fromEntries(demoServices.map(s=>[s.id,syntheticSeries(s,24)]));
const incident='POC-DEMO-001';
const run='POC-RUN-001';
const events=Object.fromEntries(demoServices.map(s=>[s.id,[{id:s.id,time:'T0 · fictif',title:'Observation synthétique',detail:s.health}]]));
const context={mode:'demo' as const,workspace:'Commerce POC',environment:'Simulation locale',source:'Fixtures synthétiques · aucune connexion runtime'};
type Props={pages?:MissionControlProps['pages']};
export function PocDemo({pages}:Props={}){
 const [page,setPage]=useState<MissionPage>('Vue globale');
 const [selected,setSelected]=useState<string|null>(null);
 const [preview,setPreview]=useState(false);
 const fallback:MissionControlProps['pages']={
 'Incidents':({navigate,selectService})=><Panel title="Incident synthétique · paiement"><p>{incident} · {run} · paiement critique (fixture)</p><button onClick={()=>{navigate('Digital Twin');selectService('payment')}}>Inspecter le CI dans le Twin</button></Panel>,
 'Intelligence':()=> <><Panel title="Analyste · exemple déterministe"><p>Hypothèse : latence du paiement et dépendance PostgreSQL.</p><p>Impact potentiel : {upstreamImpact(demoServices,'payment').join(', ')||'UNKNOWN'}</p></Panel><Panel title="Critic · exemple déterministe"><p>HOLD_FOR_HUMAN_REVIEW · causalité non attestée. Aucun appel LLM.</p></Panel></>,
 'Automatisation':()=> <><Panel title="Policy / HITL · fixture"><p>DENY_LIVE_ACTION · validation humaine requise.</p></Panel><Panel title="Prévisualisation locale"><p>Aucune exécution distante ni modification du Twin.</p><button onClick={()=>setPreview(true)}>Afficher le scénario hypothétique</button>{preview&&<p role="status">Hypothèse illustrative : paiement HEALTHY. Rétablissement réel UNKNOWN. Aucun reçu serveur.</p>}</Panel></>,
 'Evidence':()=> <Panel title="Checkpoints synthétiques"><p>{incident} / {run} · aucune preuve runtime.</p><Timeline events={[{id:'1',time:'T0 · fictif',title:'Observation',detail:'Fixture locale'},{id:'2',time:'T1 · fictif',title:'Analyse',detail:'Hypothèse illustrative'},{id:'3',time:'Non exécuté',title:'Preuve de rétablissement',detail:'MISSING'}]}/>{preview&&<p>Prévisualisation locale consultée · aucun reçu serveur.</p>}</Panel>,
 'ITSM':()=> <Panel title="ITSM · aperçu synthétique"><p>{incident} · ticket réel UNKNOWN · aucun handoff effectué.</p><p>GLPI / Temporal / n8n : intégrations non qualifiées dans ce POC local.</p></Panel>
 };
 return <div className="ux-poc-demo"><MissionControl services={demoServices} history={history} events={events} context={context} page={page} onPageChange={p=>{setPage(p);setSelected(null)}} selectedServiceId={selected} onSelectionChange={setSelected} pages={{...fallback,...pages}}/></div>;
}
