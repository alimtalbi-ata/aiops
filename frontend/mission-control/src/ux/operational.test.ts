import {availabilityStats,difference,severityRank,type Comparison} from './operational';
function eq(a:unknown,b:unknown){if(!Object.is(a,b))throw Error('Expected '+b+' got '+a);}
eq(availabilityStats([]).upRatio,null);
eq(availabilityStats([{at:0,up:null}]).upRatio,null);
eq(availabilityStats([{at:0,up:0}]).upRatio,0);
eq(availabilityStats([{at:0,up:1},{at:60,up:null}]).coverage,.5);
eq(availabilityStats([{at:0,up:1},{at:60,up:0}]).upRatio,.5);
const c:Comparison={id:'test',label:'test',unit:'s',source:'test',before:{at:0,value:2},after:{at:60,value:0}};
eq(difference(c),-2);
eq(difference({...c,after:{at:60,value:null}}),null);
eq(difference({...c,after:{at:0,value:1}}),null);
eq(severityRank('P1'),0);
eq(severityRank('UNKNOWN'),4);
