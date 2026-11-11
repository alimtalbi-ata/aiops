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
