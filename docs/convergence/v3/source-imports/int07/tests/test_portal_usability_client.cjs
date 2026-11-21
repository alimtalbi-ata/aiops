const test = require('node:test');
const assert = require('node:assert/strict');
const {mount} = require('../app/portal/portal_usability.js');
const row = (...values) => ({hidden:false,cells:values.map(textContent=>({tagName:'TD',colSpan:1,textContent}))});
function fixture(rows) {
  const body={rows}, filter={hidden:true}, result={textContent:''};
  const input={value:'',listeners:{},addEventListener(k,f){this.listeners[k]=f},focus(){}};
  const clear={listeners:{},addEventListener(k,f){this.listeners[k]=f}};
  const nodes={'portal-runs':body,'portal-run-filter':filter,'portal-run-filter-input':input,'portal-run-filter-clear':clear,'portal-run-filter-result':result};
  const doc={getElementById:id=>nodes[id]};
  mount(doc);
  return {input,clear,result,filter,search(q){input.value=q;input.listeners.input()}};
}
test('local search finds row 16 and resets',()=>{
  const rows=Array.from({length:20},(_,i)=>row('TEST-'+i,'DEMO',i===15?'BLOCKED':'DONE','UNKNOWN','SYNTHETIC'));
  const f=fixture(rows); f.search(' blocked ');
  assert.equal(rows.filter(r=>!r.hidden).length,1);
  assert.equal(rows[15].hidden,false);
  assert.match(f.result.textContent,/^1 \/ 20/);
  f.clear.listeners.click(); assert.equal(rows.filter(r=>!r.hidden).length,20);
});
test('UNKNOWN source is never hidden or counted',()=>{
  const unknown=row('UNKNOWN'); unknown.cells[0].colSpan=5;
  const f=fixture([unknown]); f.search('missing');
  assert.equal(unknown.hidden,false); assert.equal(f.input.disabled,true);
  assert.match(f.result.textContent,/Filtre indisponible/);
});
test('no match leaves source state visible',()=>{
  const unknown=row('UNKNOWN'); unknown.cells[0].colSpan=5;
  const data=row('TEST','DEMO','BLOCKED','UNKNOWN','SYNTHETIC');
  const f=fixture([unknown,data]); f.search('missing');
  assert.equal(unknown.hidden,false);assert.equal(data.hidden,true);
  assert.match(f.result.textContent,/^0 \/ 1/);
});
