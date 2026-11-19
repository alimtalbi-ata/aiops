import {MissionControl} from './MissionControl';
import {demoServices} from './model';
import {syntheticSeries} from './analytics';
const history=Object.fromEntries(demoServices.map(s=>[s.id,syntheticSeries(s,24)]));
const events=Object.fromEntries(demoServices.map(s=>[s.id,[{id:s.id,time:'10:00 · fictif',title:'Observation synthétique',detail:s.health}]]));
export function MissionControlDemo({embedded=false}:{embedded?:boolean}={}){
 return <MissionControl services={demoServices} history={history} events={events} embedded={embedded} context={{mode:'demo',workspace:'Commerce',environment:'Simulation',source:'Fixtures synthétiques'}}/>;
}
