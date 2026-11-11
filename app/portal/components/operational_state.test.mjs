import test from 'node:test';
import assert from 'node:assert/strict';
import {deriveOperationalState,createLatestReader,renderOperationalState} from './operational_state.mjs';
const now=Date.parse('2026-11-10T16:25:00Z'),fresh='2026-11-10T16:24:00Z';
test('freshness fail closed and explicit states',()=>{
 assert.equal(deriveOperationalState({records:[1],observedAt:fresh,now}),'READY');
 assert.equal(deriveOperationalState({records:[],observedAt:fresh,now}),'EMPTY');
 for(const observedAt of [null,'invalid','2026-11-10T16:20:00Z','2026-11-10T16:26:00Z'])
  assert.equal(deriveOperationalState({records:[1],observedAt,now}),'UNKNOWN');
 assert.equal(deriveOperationalState({records:null,observedAt:fresh,now}),'UNKNOWN');
 assert.equal(deriveOperationalState({loading:true,now}),'LOADING');
 assert.equal(deriveOperationalState({error:new Error('offline'),now}),'ERROR');
});
test('rapid requests cannot publish stale success or errors',async()=>{
 const pending=[],published=[];
 const reader=createLatestReader((q,{signal})=>new Promise((resolve,reject)=>pending.push({q,signal,resolve,reject})),x=>published.push(x),{now:()=>now});
 const first=reader.load('1h'),second=reader.load('6h');
 assert.equal(pending[0].signal.aborted,true);
 pending[1].resolve({records:['new'],observed_at:fresh,scope_verified:true,authorization_source:'server'});await second;
 pending[0].resolve(['old']);await first;
 assert.deepEqual(published.map(x=>x.state),['LOADING','LOADING','READY']);
 assert.deepEqual(published.at(-1).result.records,['new']);
 const third=reader.load('24h');reader.cancel();pending[2].reject(new Error('late'));await third;
 assert.deepEqual(published.at(-1),{state:'UNKNOWN',result:null});
});
test('untrusted detail stays text; retry is native keyboard button',()=>{
 class Element{
  constructor(tag,doc){this.tag=tag;this.ownerDocument=doc;this.attributes={};this.children=[];this.textContent='';}
  setAttribute(k,v){this.attributes[k]=v;}
  append(...xs){this.children.push(...xs);}
  replaceChildren(...xs){this.children=xs;}
  addEventListener(k,cb){this[k]=cb;}
 }
 const doc={createElement(tag){return new Element(tag,doc)}};
 const root=new Element('div',doc);let retries=0;
 const section=renderOperationalState(root,'ERROR',{details:'<script>alert(1)</script>',retry:()=>retries++});
 assert.equal(section.attributes.role,'alert');
 assert.match(section.children[1].textContent,/<script>/);
 assert.equal(section.children[2].tag,'button');section.children[2].click();assert.equal(retries,1);
 assert.equal(renderOperationalState(root,'BOGUS').attributes['data-operational-state'],'UNKNOWN');
});

test('read model must never promote unscoped, stale, missing or future evidence',async()=>{
 const published=[];
 const envelopes=[
  {records:[1],observed_at:fresh,scope_verified:false,authorization_source:'server'},
  {records:[1],observed_at:fresh,scope_verified:true,authorization_source:'browser'},
  {records:[1],observed_at:'2026-11-10T16:20:00Z',scope_verified:true,authorization_source:'server'},
  {records:[1],observed_at:'2026-11-10T16:26:00Z',scope_verified:true,authorization_source:'server'},
  {records:[1],scope_verified:true,authorization_source:'server'},
  [1],
 ];
 const reader=createLatestReader(async()=>envelopes.shift(),x=>published.push(x),{now:()=>now});
 for(let i=0;i<6;i++)await reader.load(i);
 assert.equal(published.filter(x=>x.state==='UNKNOWN').length,6);
 assert.ok(published.filter(x=>x.state==='UNKNOWN').every(x=>x.result===null));
});
test('qualified empty result remains EMPTY, transport error remains ERROR',async()=>{
 const published=[];
 let fail=false;
 const reader=createLatestReader(async()=>{if(fail)throw new Error('offline');return {records:[],observed_at:fresh,scope_verified:true,authorization_source:'server'}},x=>published.push(x),{now:()=>now});
 await reader.load('empty');fail=true;await reader.load('error');
 assert.deepEqual(published.map(x=>x.state),['LOADING','EMPTY','LOADING','ERROR']);
});

test('transport failures never expose secrets or raw error objects to UI',async()=>{
 const published=[];
 const secret='Bearer super-secret-token';
 const reader=createLatestReader(async()=>{throw new Error('GET https://api.invalid/?token='+secret)},x=>published.push(x),{now:()=>now});
 await reader.load('incidents');
 assert.deepEqual(published,[{state:'LOADING'},{state:'ERROR',error_code:'READ_FAILED',result:null}]);
 assert.equal(JSON.stringify(published).includes(secret),false);
 assert.equal(JSON.stringify(published).includes('api.invalid'),false);
});

test('transport exception publishes terminal ERROR, never leaves UI stuck LOADING',async()=>{
 const states=[];
 const reader=createLatestReader(async()=>{throw new TypeError('network failed')},event=>states.push(event),{now:()=>now});
 await reader.load('runs');
 assert.deepEqual(states,[{state:'LOADING'},{state:'ERROR',error_code:'READ_FAILED',result:null}]);
 assert.equal(JSON.stringify(states).includes('network failed'),false);
});

test('hung read times out to UNKNOWN and ignores late success',async()=>{
 const published=[];let finish,signal;
 const reader=createLatestReader((_,ctx)=>{signal=ctx.signal;return new Promise(resolve=>{finish=resolve})},x=>published.push(x),{now:()=>now,timeoutMs:10});
 await reader.load('hung');
 assert.deepEqual(published.map(x=>x.state),['LOADING','UNKNOWN']);
 assert.equal(published[1].reason,'TIMEOUT');
 assert.equal(published[1].result,null);
 assert.equal(signal.aborted,true);
 finish({records:[1],observed_at:fresh,scope_verified:true,authorization_source:'server'});
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(published.length,2);
});
test('newer request fences a previous timeout and invalid budgets fail closed',async()=>{
 assert.throws(()=>createLatestReader(()=>{},()=>{},{timeoutMs:0}),RangeError);
 assert.throws(()=>createLatestReader(()=>{},()=>{},{timeoutMs:Infinity}),RangeError);
 const published=[];let release;
 const reader=createLatestReader(q=>q==='slow'?new Promise(resolve=>{release=resolve}):Promise.resolve({records:[],observed_at:fresh,scope_verified:true,authorization_source:'server'}),x=>published.push(x),{now:()=>now,timeoutMs:20});
 const slow=reader.load('slow');await reader.load('fast');
 await new Promise(resolve=>setTimeout(resolve,30));
 release({records:[1],observed_at:fresh,scope_verified:true,authorization_source:'server'});
 await slow;
 assert.deepEqual(published.map(x=>x.state),['LOADING','LOADING','EMPTY']);
});


test('cancelled pending read terminates as UNKNOWN and ignores late sensitive response',async()=>{
 const events=[];let resolve;
 const reader=createLatestReader(()=>new Promise(r=>{resolve=r}),x=>events.push(x),{now:()=>now});
 const pending=reader.load('evidence');
 reader.cancel();
 resolve({records:['cross-tenant'],observed_at:fresh,scope_verified:true,authorization_source:'server'});
 await pending;
 assert.deepEqual(events,[{state:'LOADING'},{state:'UNKNOWN',result:null}]);
 reader.cancel();
 assert.equal(events.length,2,'idle cancel must not duplicate events');
});

test('transport cannot impersonate timeout using a reserved error message',async()=>{
 const events=[];
 const reader=createLatestReader(async()=>{throw new Error('OPERATIONAL_TIMEOUT')},x=>events.push(x),{now:()=>now,timeoutMs:500});
 await reader.load('incidents');
 assert.deepEqual(events,[{state:'LOADING'},{state:'ERROR',error_code:'READ_FAILED',result:null}]);
});

test('transport error with timeout-like message never reveals sensitive details',async()=>{
 const events=[];
 const reader=createLatestReader(async()=>{throw {message:'OPERATIONAL_TIMEOUT',token:'secret-tenant-token'}},x=>events.push(x),{now:()=>now});
 await reader.load('evidence');
 assert.deepEqual(events.at(-1),{state:'ERROR',error_code:'READ_FAILED',result:null});
 assert.equal(JSON.stringify(events).includes('secret-tenant-token'),false);
});


test('latest reader enforces bounded source-specific freshness without promoting stale data',async()=>{
 const events=[];
 const reader=createLatestReader(async()=>({records:[{id:'run-1'}],observed_at:fresh,scope_verified:true,authorization_source:'server'}),event=>events.push(event),{now:()=>now,maxAgeMs:30000});
 await reader.load('runs');
 assert.deepEqual(events,[{state:'LOADING'},{state:'UNKNOWN',result:null}]);
});

test('latest reader accepts qualified evidence within a configured freshness budget',async()=>{
 const events=[];
 const reader=createLatestReader(async()=>({records:[{id:'run-1'}],observed_at:fresh,scope_verified:true,authorization_source:'server'}),event=>events.push(event),{now:()=>now,maxAgeMs:60000});
 await reader.load('runs');
 assert.deepEqual(events.map(e=>e.state),['LOADING','READY']);
 assert.equal(events[1].result.records[0].id,'run-1');
});

test('invalid freshness budgets fail before any network read or UI publication',()=>{
 let reads=0,publishes=0;
 for(const maxAgeMs of [0,-1,1.5,NaN,Infinity,86400001,'60000',null]){
  assert.throws(()=>createLatestReader(()=>{reads++},()=>{publishes++},{maxAgeMs}),RangeError);
 }
 assert.equal(reads,0);
 assert.equal(publishes,0);
});

test('tight freshness budget cannot override missing server authorization',async()=>{
 const events=[];
 const reader=createLatestReader(async()=>({records:[{id:'cross-tenant'}],observed_at:fresh,scope_verified:true,authorization_source:'browser'}),e=>events.push(e),{now:()=>now,maxAgeMs:60000});
 await reader.load('evidence');
 assert.deepEqual(events.at(-1),{state:'UNKNOWN',result:null});
});

test('inherited qualification cannot authorize a read-only projection',async()=>{
 const events=[];
 const inheritedScope=Object.assign(Object.create({scope_verified:true}),{
  records:[{id:'other-tenant'}],observed_at:fresh,authorization_source:'server'
 });
 const inheritedAuth=Object.assign(Object.create({authorization_source:'server'}),{
  records:[{id:'other-tenant'}],observed_at:fresh,scope_verified:true
 });
 const inheritedRecords=Object.assign(Object.create({records:[{id:'other-tenant'}]}),{
  observed_at:fresh,scope_verified:true,authorization_source:'server'
 });
 const inheritedTime=Object.assign(Object.create({observed_at:fresh}),{
  records:[{id:'other-tenant'}],scope_verified:true,authorization_source:'server'
 });
 const values=[inheritedScope,inheritedAuth,inheritedRecords,inheritedTime];
 const reader=createLatestReader(async()=>values.shift(),e=>events.push(e),{now:()=>now});
 for(let i=0;i<4;i++)await reader.load('evidence');
 assert.deepEqual(events.filter(e=>e.state!=='LOADING'),Array.from({length:4},()=>({state:'UNKNOWN',result:null})));
 assert.equal(JSON.stringify(events).includes('other-tenant'),false);
});

test('own server qualification fields still permit fresh empty read-only results',async()=>{
 const events=[];
 const reader=createLatestReader(async()=>({
  records:[],observed_at:fresh,scope_verified:true,authorization_source:'server'
 }),e=>events.push(e),{now:()=>now});
 await reader.load('runs');
 assert.deepEqual(events.map(e=>e.state),['LOADING','EMPTY']);
});

test('qualified read strips transport-only metadata and secrets from published envelope',async()=>{
 const events=[];
 const secret='Bearer should-not-reach-portal';
 const response={
  records:[{id:'run-1'}],observed_at:fresh,scope_verified:true,authorization_source:'server',
  authorization:'Bearer '+secret,headers:{cookie:'session-secret'},debug_url:'https://internal.invalid/?token='+secret,
  actor_id:'unverified-actor',tenant_id:'unverified-tenant'
 };
 const reader=createLatestReader(async()=>response,event=>events.push(event),{now:()=>now});
 await reader.load('runs');
 assert.equal(events.at(-1).state,'READY');
 assert.deepEqual(Object.keys(events.at(-1).result).sort(),['authorization_source','observed_at','records','scope_verified']);
 assert.equal(events.at(-1).result.records[0].id,'run-1');
 assert.equal(JSON.stringify(events).includes(secret),false);
 assert.equal(JSON.stringify(events).includes('session-secret'),false);
 assert.equal(JSON.stringify(events).includes('unverified-tenant'),false);
});

test('unqualified envelope with sensitive metadata publishes only UNKNOWN and null',async()=>{
 const events=[];
 const reader=createLatestReader(async()=>({
  records:[{id:'other-tenant'}],observed_at:fresh,scope_verified:false,
  authorization_source:'server',headers:{authorization:'Bearer private'}
 }),event=>events.push(event),{now:()=>now});
 await reader.load('evidence');
 assert.deepEqual(events.at(-1),{state:'UNKNOWN',result:null});
 assert.equal(JSON.stringify(events).includes('private'),false);
});
