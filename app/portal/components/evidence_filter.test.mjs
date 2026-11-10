import test from 'node:test';
import assert from 'node:assert/strict';
import {filterEvidence,mountEvidenceFilter} from './evidence_filter.mjs';
const synthetic=[{id:'synthetic-1',label:'Disque lent',status:'READY'},{id:'synthetic-2',label:'Réseau inconnu',status:'UNKNOWN'},{id:'synthetic-1',label:'Doublon',status:'READY'}];
test('synthetic task filtering, deduplication and empty state',()=>{
 assert.deepEqual(filterEvidence(synthetic,{query:'disque'}).records.map(x=>x.id),['synthetic-1']);
 assert.deepEqual(filterEvidence(synthetic,{status:'UNKNOWN'}).records.map(x=>x.id),['synthetic-2']);
 assert.equal(filterEvidence(synthetic,{query:'absent'}).state,'EMPTY');
 assert.equal(filterEvidence(synthetic).records.length,2);
});
test('malformed or unverified input is UNKNOWN, not EMPTY',()=>{
 for(const records of [null,{},[{id:'x',label:'a',status:'LIVE'}]])assert.equal(filterEvidence(records).state,'UNKNOWN');
 assert.equal(filterEvidence(synthetic,{query:'x'.repeat(257)}).state,'UNKNOWN');
 assert.equal(filterEvidence(synthetic,{status:'RESOLVED'}).state,'UNKNOWN');
});
test('native keyboard controls, live count, and no HTML interpretation',()=>{
 class Element{constructor(tag,doc){this.tag=tag;this.ownerDocument=doc;this.children=[];this.attrs={};this.value=tag==='select'?'ALL':'';this.textContent='';this.events={};}setAttribute(k,v){this.attrs[k]=v;}append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}addEventListener(k,fn){this.events[k]=fn;}}
 const doc={createElement(tag){return new Element(tag,doc)}};const root=new Element('div',doc);const seen=[];
 const mounted=mountEvidenceFilter(root,{records:[{id:'synthetic-x',label:'<img src=x onerror=alert(1)>',status:'READY'}],onChange:r=>seen.push(r.state)});
 const form=root.children[0],input=form.children[0].children[0],output=form.children[2],list=form.children[3];
 assert.equal(form.attrs.role,'search');assert.equal(input.type,'search');assert.equal(output.attrs['aria-live'],'polite');
 assert.equal(list.children[0].textContent.includes('<img'),true);
 input.value='missing';input.events.input();assert.match(output.textContent,/0 preuve/);
 mounted.setRecords(null);assert.equal(seen.at(-1),'UNKNOWN');assert.equal(list.children.length,0);
});
