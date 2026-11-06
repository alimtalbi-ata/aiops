import test from 'node:test';
import assert from 'node:assert/strict';
import {mountFsReal} from './fs-real-readonly.mjs';

const tick = () => new Promise(resolve => setImmediate(resolve));
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes,no) => {resolve=yes;reject=no;});
  return {promise,resolve,reject};
}
function element() {
  return {
    textContent:'', children:[], handlers:{},
    setAttribute(){},
    addEventListener(type,fn){this.handlers[type]=fn;},
    replaceChildren(...children){this.children=children;}
  };
}
function fixture() {
  const original=globalThis.document;
  globalThis.document={createElement:()=>element()};
  const root=element();
  return {root,restore:()=>{globalThis.document=original;}};
}
const projection=(mode)=>({
  mode,glpi_ticket_id:147,synthetic:true,no_live_effects:true,
  core:{state:'BLOCKED'},temporal:{state:'UNKNOWN'},policy:{state:'BLOCKED'},
  questions:mode==='insufficient'?['Quelle est la politique de rétention ?']:[]
});
const response=(mode)=>({
  ok:true,headers:{get:()=> 'application/json'},json:async()=>projection(mode)
});
test('two buttons render real backend projection and human questions',async()=>{
  const {root,restore}=fixture();
  try {
    const dispose=mountFsReal(root,async url=>response(new URL(url,'https://portal.invalid').searchParams.get('mode')));
    assert.equal(root.children.length,3);
    assert.match(root.children[2].textContent,/UNAVAILABLE/);
    assert.match(root.children[2].textContent,/fraîcheur\/approbation\/résolution non attestées/);
    await root.children[0].handlers.click();
    assert.match(root.children[2].textContent,/Core: BLOCKED/);
    assert.match(root.children[2].textContent,/Freshness: NOT_ATTESTED/);
    assert.match(root.children[2].textContent,/Resolution: NOT_ATTESTED/);
    await root.children[1].handlers.click();
    assert.match(root.children[2].textContent,/politique de rétention/);
    dispose();
    assert.equal(root.children.length,0);
  } finally {restore();}
});
test('late response cannot overwrite newer insufficient-data state',async()=>{
  const {root,restore}=fixture();
  try {
    const old=deferred();
    const dispose=mountFsReal(root,(url)=>url.includes('lab147')?old.promise:Promise.resolve(response('insufficient')));
    const first=root.children[0].handlers.click();
    await root.children[1].handlers.click();
    old.resolve(response('lab147'));
    await first;await tick();
    assert.match(root.children[2].textContent,/politique de rétention/);
    dispose();
  } finally {restore();}
});
test('dispose invalidates pending response even when fetch ignores abort',async()=>{
  const {root,restore}=fixture();
  try {
    const pending=deferred();
    const dispose=mountFsReal(root,()=>pending.promise);
    const first=root.children[0].handlers.click();
    dispose();
    pending.resolve(response('lab147'));
    await first;
    assert.equal(root.children.length,0);
  } finally {restore();}
});
