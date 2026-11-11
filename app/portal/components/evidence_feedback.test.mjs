import test from 'node:test';
import assert from 'node:assert/strict';
import {evidenceFeedback,mountEvidenceFeedback} from './evidence_feedback.mjs';
const syntheticStates=['LOADING','EMPTY','ERROR','UNKNOWN'];
test('synthetic feedback states are distinct and fail closed',()=>{
  assert.equal(new Set(syntheticStates.map(s=>evidenceFeedback(s).message)).size,4);
  for(const s of [null,undefined,'READY','<img src=x>'])
    assert.deepEqual(evidenceFeedback(s),evidenceFeedback('UNKNOWN'));
});
test('synthetic transitions replace stale feedback and use native ARIA',()=>{
  class Element{
    constructor(tag){this.tag=tag;this.attrs={};this.children=[];this.textContent='';}
    setAttribute(k,v){this.attrs[k]=v;}
    getAttribute(k){return this.attrs[k]??null;}
    replaceChildren(...children){this.children=children;}
  }
  const doc={createElement:tag=>new Element(tag)};
  const root=new Element('div');root.ownerDocument=doc;
  const loading=mountEvidenceFeedback(root,'LOADING');
  assert.equal(loading.attrs.role,'status');
  assert.equal(loading.attrs['aria-busy'],'true');
  assert.equal(root.attrs['aria-busy'],'true');
  const error=mountEvidenceFeedback(root,'ERROR');
  assert.equal(root.children.length,1);
  assert.equal(root.children[0],error);
  assert.equal(error.attrs.role,'alert');
  assert.equal(error.attrs['aria-live'],'assertive');
  assert.equal(root.attrs['aria-busy'],'false');
  const unknown=mountEvidenceFeedback(root,'NOT_AUTHORIZED');
  assert.equal(unknown.textContent,evidenceFeedback('UNKNOWN').message);
  assert.equal(unknown.attrs.role,'status');
  assert.equal(unknown.attrs['aria-atomic'],'true');
  assert.equal(Object.hasOwn(unknown.attrs,'aria-busy'),false);
  assert.equal(root.attrs['aria-busy'],'false');
});
test('synthetic LOADING to EMPTY and UNKNOWN always clears stable region busy state',()=>{
  class Element{
    constructor(){this.attrs={};this.ownerDocument={createElement:()=>new Element()};}
    setAttribute(k,v){this.attrs[k]=v;}
    getAttribute(k){return this.attrs[k]??null;}
    replaceChildren(...children){this.children=children;}
  }
  for(const next of ['EMPTY','UNKNOWN','UNRECOGNIZED']){
    const root=new Element();
    mountEvidenceFeedback(root,'LOADING');
    assert.equal(root.attrs['aria-busy'],'true');
    mountEvidenceFeedback(root,next);
    assert.equal(root.attrs['aria-busy'],'false');
    assert.equal(root.children[0].attrs['aria-busy'],undefined);
  }
});
test('invalid mount root is rejected',()=>{
  assert.throws(()=>mountEvidenceFeedback(null,'LOADING'),TypeError);
});

test('synthetic polling does not repeat identical live-region announcements',()=>{
  class Element{
    constructor(){this.attrs={};this.children=[];this.replacements=0;this.ownerDocument={createElement:()=>new Element()};}
    setAttribute(k,v){this.attrs[k]=v;}
    getAttribute(k){return this.attrs[k]??null;}
    replaceChildren(...nodes){this.children=nodes;this.replacements++;}
    get firstChild(){return this.children[0]??null;}
    get childNodes(){return this.children;}
  }
  const root=new Element();
  const first=mountEvidenceFeedback(root,'LOADING');
  assert.equal(mountEvidenceFeedback(root,'LOADING'),first);
  assert.equal(root.replacements,1);
  const error=mountEvidenceFeedback(root,'ERROR');
  assert.notEqual(error,first);
  assert.equal(root.replacements,2);
  assert.equal(root.attrs['aria-busy'],'false');
  assert.equal(mountEvidenceFeedback(root,'ERROR'),error);
  assert.equal(root.replacements,2);
  // A separately updated DOM must be repaired, not treated as a cached announcement.
  root.replaceChildren();
  const repaired=mountEvidenceFeedback(root,'ERROR');
  assert.notEqual(repaired,error);
  assert.equal(root.replacements,4);
  assert.equal(repaired.attrs.role,'alert');
});

test('synthetic external DOM drift repairs busy flag without repeated announcement',()=>{
  class Element{
    constructor(){this.attrs={};this.children=[];this.replacements=0;this.ownerDocument={createElement:()=>new Element()};}
    setAttribute(k,v){this.attrs[k]=v;}
    getAttribute(k){return this.attrs[k]??null;}
    replaceChildren(...nodes){this.children=nodes;this.replacements++;}
    get firstChild(){return this.children[0]??null;}
    get childNodes(){return this.children;}
  }
  const root=new Element();
  const node=mountEvidenceFeedback(root,'LOADING');
  root.setAttribute('aria-busy','false');
  assert.equal(mountEvidenceFeedback(root,'LOADING'),node);
  assert.equal(root.attrs['aria-busy'],'true');
  assert.equal(root.replacements,1);
  root.children.push(new Element());
  const repaired=mountEvidenceFeedback(root,'LOADING');
  assert.notEqual(repaired,node);
  assert.equal(root.childNodes.length,1);
  assert.equal(root.replacements,2);
  assert.equal(root.attrs['aria-busy'],'true');
});

test('synthetic external mutation of cached live-region node is repaired',()=>{
  class Element{
    constructor(){this.attrs={};this.children=[];this.replacements=0;this.textContent='';this.ownerDocument={createElement:()=>new Element()};}
    setAttribute(k,v){this.attrs[k]=v;}
    getAttribute(k){return this.attrs[k]??null;}
    replaceChildren(...nodes){this.children=nodes;this.replacements++;}
    get firstChild(){return this.children[0]??null;}
    get childNodes(){return this.children;}
  }
  for(const state of ['LOADING','ERROR','UNKNOWN']){
    for(const corrupt of [
      node=>{node.textContent='Donnée synthétique erronée';},
      node=>node.setAttribute('role','presentation'),
      node=>node.setAttribute('aria-live','off'),
      node=>node.setAttribute('aria-atomic','false'),
      node=>node.setAttribute('aria-busy','false')
    ]){
      const root=new Element();
      const original=mountEvidenceFeedback(root,state);
      corrupt(original);
      const repaired=mountEvidenceFeedback(root,state);
      assert.notEqual(repaired,original);
      assert.equal(root.children.length,1);
      assert.equal(repaired.textContent,evidenceFeedback(state).message);
      assert.equal(repaired.getAttribute('role'),state==='ERROR'?'alert':'status');
      assert.equal(repaired.getAttribute('aria-live'),state==='ERROR'?'assertive':'polite');
      assert.equal(repaired.getAttribute('aria-atomic'),'true');
      assert.equal(repaired.getAttribute('aria-busy'),state==='LOADING'?'true':null);
      assert.equal(root.getAttribute('aria-busy'),state==='LOADING'?'true':'false');
      assert.equal(mountEvidenceFeedback(root,state),repaired);
      assert.equal(root.replacements,2);
    }
  }
});

test('synthetic nested markup injection is repaired even when text is unchanged',()=>{
  class Element{
    constructor(){this.attrs={};this.children=[];this.textContent='';this.replacements=0;this.ownerDocument={createElement:()=>new Element()};}
    setAttribute(k,v){this.attrs[k]=v;}
    getAttribute(k){return this.attrs[k]??null;}
    replaceChildren(...nodes){this.children=nodes;this.replacements++;}
    get childNodes(){return this.children;}
    get firstChild(){return this.children[0]??null;}
  }
  const root=new Element();
  const first=mountEvidenceFeedback(root,'UNKNOWN');
  assert.equal(mountEvidenceFeedback(root,'UNKNOWN'),first);
  // An external renderer adds an empty focusable element without changing the message.
  first.children.push(new Element());
  assert.equal(first.textContent,evidenceFeedback('UNKNOWN').message);
  const repaired=mountEvidenceFeedback(root,'UNKNOWN');
  assert.notEqual(repaired,first);
  assert.equal(repaired.childNodes.length,0);
  assert.equal(repaired.getAttribute('role'),'status');
  assert.equal(root.replacements,2);
  assert.equal(mountEvidenceFeedback(root,'UNKNOWN'),repaired);
});

test('synthetic external hiding of an announcement is repaired without hiding the replacement',()=>{
  class Element{
    constructor(){this.attrs={};this.children=[];this.textContent='';this.replacements=0;this.ownerDocument={createElement:()=>new Element()};}
    setAttribute(k,v){this.attrs[k]=v;}
    getAttribute(k){return this.attrs[k]??null;}
    replaceChildren(...nodes){this.children=nodes;this.replacements++;}
    get childNodes(){return this.children;}
    get firstChild(){return this.children[0]??null;}
  }
  for(const state of ['LOADING','EMPTY','ERROR','UNKNOWN']){
    for(const attr of ['aria-hidden','hidden']){
      const root=new Element();
      const first=mountEvidenceFeedback(root,state);
      assert.equal(mountEvidenceFeedback(root,state),first);
      first.setAttribute(attr,attr==='hidden'?'':'true');
      const repaired=mountEvidenceFeedback(root,state);
      assert.notEqual(repaired,first);
      assert.equal(repaired.getAttribute(attr),null);
      assert.equal(repaired.textContent,evidenceFeedback(state).message);
      assert.equal(root.getAttribute('aria-busy'),state==='LOADING'?'true':'false');
      assert.equal(root.replacements,2);
      assert.equal(mountEvidenceFeedback(root,state),repaired);
    }
  }
});

test('synthetic inert announcement is reconstructed for all feedback states',()=>{
  class Element{
    constructor(){this.attrs={};this.children=[];this.textContent='';this.replacements=0;this.ownerDocument={createElement:()=>new Element()};}
    setAttribute(k,v){this.attrs[k]=v;}
    getAttribute(k){return this.attrs[k]??null;}
    replaceChildren(...nodes){this.children=nodes;this.replacements++;}
    get childNodes(){return this.children;}
    get firstChild(){return this.children[0]??null;}
  }
  for(const state of syntheticStates){
    const root=new Element();
    const first=mountEvidenceFeedback(root,state);
    assert.equal(mountEvidenceFeedback(root,state),first);
    first.setAttribute('inert','');
    const repaired=mountEvidenceFeedback(root,state);
    assert.notEqual(repaired,first);
    assert.equal(repaired.getAttribute('inert'),null);
    assert.equal(repaired.textContent,evidenceFeedback(state).message);
    assert.equal(repaired.getAttribute('role'),state==='ERROR'?'alert':'status');
    assert.equal(root.getAttribute('aria-busy'),state==='LOADING'?'true':'false');
    assert.equal(root.replacements,2);
    assert.equal(mountEvidenceFeedback(root,state),repaired);
  }
});
