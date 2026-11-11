import test from 'node:test';
import assert from 'node:assert/strict';
import {filterEvidence,mountEvidenceFilter} from './evidence_filter.mjs';
const synthetic=[{id:'synthetic-1',label:'Disque lent',status:'READY'},{id:'synthetic-2',label:'Réseau inconnu',status:'UNKNOWN'},{id:'synthetic-1',label:'Disque lent',status:'READY'}];
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
 const form=root.children[0],input=form.children[0].children[0],output=form.children[2],list=form.children[4];
 assert.equal(form.attrs.role,'search');assert.equal(input.type,'search');assert.equal(output.attrs['aria-live'],'polite');
 assert.equal(list.children[0].textContent.includes('<img'),true);
 assert.match(list.children[0].textContent,/Disponible/);
 assert.doesNotMatch(list.children[0].textContent,/READY/);
 input.value='missing';input.events.input();assert.match(output.textContent,/Aucune preuve ne correspond aux filtres/);
 mounted.setRecords(null);assert.equal(seen.at(-1),'UNKNOWN');assert.equal(list.children.length,0);
});

test('synthetic conflicting duplicate evidence is UNKNOWN, not silently first-wins',()=>{
 const a={id:'synthetic-7',label:'Preuve A',status:'READY'};
 for(const b of [
  {...a,label:'Preuve B'},
  {...a,status:'ERROR'}
 ]){
  const result=filterEvidence([a,b],{query:'Preuve A',status:'READY'});
  assert.deepEqual(result,{state:'UNKNOWN',records:[]});
 }
 assert.equal(filterEvidence([a,{...a}]).records.length,1);
});

test('synthetic empty source and unmatched filters have distinct accessible announcements',()=>{
 class Element {
  constructor(tag,doc){this.tag=tag;this.ownerDocument=doc;this.children=[];this.attrs={};this.value=tag==='select'?'ALL':'';this.textContent='';this.events={};}
  setAttribute(k,v){this.attrs[k]=v;}
  append(...xs){this.children.push(...xs);}
  replaceChildren(...xs){this.children=xs;}
  addEventListener(k,fn){this.events[k]=fn;}
 }
 const doc={createElement(tag){return new Element(tag,doc)}};
 const root=new Element('div',doc);
 const view=mountEvidenceFilter(root,{records:[]});
 const form=root.children[0],input=form.children[0].children[0],count=form.children[2];
 assert.equal(count.textContent,'Aucune preuve disponible');
 assert.equal(count.attrs.role,'status');
 view.setRecords([{id:'synthetic-1',label:'Disque',status:'READY'}]);
 input.value='introuvable';input.events.input();
 assert.equal(count.textContent,'Aucune preuve ne correspond aux filtres');
 view.setRecords(null);
 assert.equal(count.textContent,'Preuves non vérifiables');
 view.setRecords([{id:'synthetic-1',label:'Disque',status:'READY'}]);
 input.value='';input.events.input();
 assert.match(count.textContent,/1 résultat/);
});

test('synthetic no-match reset is keyboard operable and hidden for UNKNOWN',()=>{
 class Element {
  constructor(tag,doc){this.tag=tag;this.ownerDocument=doc;this.children=[];this.attrs={};this.value=tag==='select'?'ALL':'';this.textContent='';this.events={};this.hidden=false;this.focused=false;}
  setAttribute(k,v){this.attrs[k]=v;}append(...xs){this.children.push(...xs);}
  replaceChildren(...xs){this.children=xs;}addEventListener(k,fn){this.events[k]=fn;}
  focus(){this.focused=true;}
 }
 const doc={createElement(tag){return new Element(tag,doc)}},root=new Element('div',doc);
 const view=mountEvidenceFilter(root,{records:[{id:'synthetic-1',label:'Disk',status:'READY'}]});
 const form=root.children[0],input=form.children[0].children[0],select=form.children[1],reset=form.children[3];
 assert.equal(reset.tag,'button');assert.equal(reset.type,'button');assert.equal(reset.hidden,true);
 input.value='no match';input.events.input();assert.equal(reset.hidden,false);
 reset.events.click();assert.equal(input.value,'');assert.equal(select.value,'ALL');
 assert.equal(input.focused,true);assert.equal(reset.hidden,true);
 select.value='ERROR';select.events.change();assert.equal(reset.hidden,false);
 view.setRecords(null);assert.equal(reset.hidden,true);
});

test('synthetic evidence statuses are localized without promoting UNKNOWN to READY',()=>{
 class Element {
  constructor(tag,doc){this.tag=tag;this.ownerDocument=doc;this.children=[];this.attrs={};this.value=tag==='select'?'ALL':'';this.textContent='';this.events={};}
  setAttribute(k,v){this.attrs[k]=v;}append(...xs){this.children.push(...xs);}
  replaceChildren(...xs){this.children=xs;}addEventListener(k,fn){this.events[k]=fn;}
 }
 const doc={createElement(tag){return new Element(tag,doc)},root=new Element('div',doc);
 const rows=[{id:'synthetic-ready',label:'Disque',status:'READY'},{id:'synthetic-unknown',label:'Réseau',status:'UNKNOWN'},{id:'synthetic-error',label:'Agent',status:'ERROR'},{id:'synthetic-empty',label:'Sans preuve',status:'EMPTY'}];
 const view=mountEvidenceFilter(root,{records:rows});
 const form=root.children[0],status=form.children[1],count=form.children[2],list=form.children[4];
 assert.deepEqual(status.children.map(option=>[option.value,option.textContent]),[['ALL','Tous les états'],['READY','Disponible'],['UNKNOWN','Non vérifiable'],['ERROR','Erreur'],['EMPTY','Vide']]);

 assert.deepEqual(list.children.map(x=>x.textContent),['Disque — Disponible','Réseau — Non vérifiable','Agent — Erreur','Sans preuve — Vide']);
 assert.match(count.textContent,/4 résultat/);
 status.value='UNKNOWN';status.events.change();
 assert.deepEqual(list.children.map(x=>x.textContent),['Réseau — Non vérifiable']);
 assert.match(count.textContent,/1 résultat/);
 view.setRecords(null);assert.equal(count.textContent,'Preuves non vérifiables');
 assert.equal(list.children.length,0);
});
