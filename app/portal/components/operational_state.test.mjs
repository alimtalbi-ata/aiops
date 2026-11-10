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
 const reader=createLatestReader((q,{signal})=>new Promise((resolve,reject)=>pending.push({q,signal,resolve,reject})),x=>published.push(x));
 const first=reader.load('1h'),second=reader.load('6h');
 assert.equal(pending[0].signal.aborted,true);
 pending[1].resolve(['new']);await second;
 pending[0].resolve(['old']);await first;
 assert.deepEqual(published.map(x=>x.state),['LOADING','LOADING','READY']);
 assert.deepEqual(published.at(-1).result,['new']);
 const third=reader.load('24h');reader.cancel();pending[2].reject(new Error('late'));await third;
 assert.equal(published.at(-1).state,'LOADING');
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
