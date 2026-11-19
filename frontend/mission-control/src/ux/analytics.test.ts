import {metric,sumKnown,weightedErrors,syntheticSeries,type Sample} from './analytics';
import type {TwinService} from './model';
function equal(actual:unknown,expected:unknown){if(!Object.is(actual,expected))throw new Error('Expected '+expected+', got '+actual);}
const unknown:TwinService={id:'u',name:'Unknown',health:'UNKNOWN',rpm:null,p95:null,errors:null,calls:[]};
const sample=(rpm:number|null,errors:number|null):Sample=>({slot:0,rpm,errors,p95:null,health:'UNKNOWN'});
equal(metric(null),'—');
equal(metric(0),'0');
equal(sumKnown([0,0]),0);
equal(sumKnown([1,null]),null);
equal(sumKnown([]),null);
equal(weightedErrors([sample(0,0)]),null);
equal(weightedErrors([sample(10,0)]),0);
equal(weightedErrors([sample(10,null)]),null);
equal(weightedErrors([sample(10,2),sample(30,6)]),5);
equal(syntheticSeries(unknown,1)[0].health,'UNKNOWN');
equal(syntheticSeries(unknown,1)[0].rpm,null);
