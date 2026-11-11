import test from 'node:test';
import assert from 'node:assert/strict';
import {evidenceStateDescription,mountEvidenceStateLegend} from './evidence_state_legend.mjs';
test('synthetic canonical statuses remain distinct; unrecognized fails closed',()=>{
  assert.equal(evidenceStateDescription('READY').label,'Disponible');
  assert.equal(evidenceStateDescription('EMPTY').label,'Vide');
  assert.equal(evidenceStateDescription('ERROR').label,'Erreur');
  assert.equal(evidenceStateDescription('UNKNOWN').label,'Non vérifiable');
  assert.deepEqual(evidenceStateDescription('LIVE'),evidenceStateDescription('UNKNOWN'));
});
test('native details/summary and text-only descriptions work without inline scripts',()=>{
  class Element {
    constructor(tag,doc){this.tag=tag;this.ownerDocument=doc;this.children=[];this.textContent='';}
    append(...items){this.children.push(...items);}
    replaceChildren(...items){this.children=items;}
  }
  const doc={createElement(tag){return new Element(tag,doc);}};
  const root=new Element('div',doc);
  const details=mountEvidenceStateLegend(root);
  assert.equal(root.children[0],details);
  assert.equal(details.tag,'details');
  assert.equal(details.children[0].tag,'summary');
  assert.equal(details.children[1].tag,'dl');
  assert.deepEqual(details.children[1].children.filter(x=>x.tag==='dt').map(x=>x.textContent),
    ['Disponible','Vide','Erreur','Non vérifiable']);
  assert.equal(details.children[1].children.length,8);
});
test('invalid mount target is rejected',()=>{
  assert.throws(()=>mountEvidenceStateLegend(null),TypeError);
});

test('synthetic view refresh preserves expanded disclosure but not unrelated nodes',()=>{
  class Element {
    constructor(tag,doc){this.tagName=tag.toUpperCase();this.ownerDocument=doc;this.children=[];this.open=false;this.textContent='';}
    get firstElementChild(){return this.children[0]??null;}
    append(...items){this.children.push(...items);}
    replaceChildren(...items){this.children=items;}
  }
  const doc={createElement(tag){return new Element(tag,doc);}};
  const root=new Element('div',doc);
  const first=mountEvidenceStateLegend(root);
  assert.equal(first.open,false);
  first.open=true;
  const second=mountEvidenceStateLegend(root);
  assert.notEqual(second,first);
  assert.equal(second.open,true);
  second.open=false;
  assert.equal(mountEvidenceStateLegend(root).open,false);
  root.replaceChildren(new Element('section',doc));
  assert.equal(mountEvidenceStateLegend(root).open,false);
});

test('synthetic keyboard focus remains on summary after refresh, never stolen from another control',()=>{
  class Element {
    constructor(tag,doc){this.tagName=tag.toUpperCase();this.ownerDocument=doc;this.children=[];this.open=false;this.textContent='';}
    get firstElementChild(){return this.children[0]??null;}
    append(...items){this.children.push(...items);}
    replaceChildren(...items){this.children=items;}
    focus(){this.ownerDocument.activeElement=this;}
  }
  const doc={activeElement:null,createElement(tag){return new Element(tag,doc);}};
  const root=new Element('div',doc);
  const initial=mountEvidenceStateLegend(root);
  initial.open=true;
  initial.firstElementChild.focus();
  const next=mountEvidenceStateLegend(root);
  assert.equal(next.open,true);
  assert.equal(doc.activeElement,next.firstElementChild);
  const external=new Element('button',doc);
  external.focus();
  mountEvidenceStateLegend(root);
  assert.equal(doc.activeElement,external);
  root.replaceChildren(new Element('section',doc));
  external.focus();
  mountEvidenceStateLegend(root);
  assert.equal(doc.activeElement,external);
});
