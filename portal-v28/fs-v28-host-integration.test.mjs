import test from 'node:test';
import assert from 'node:assert/strict';
import {connectFilesystemDemo} from './fs-v28-host-integration.mjs';
const names=['incident-id','run-id','evidence-id','mode','effects','incident','core','temporal','policy','evidence','source','approval','resolution','availability','reason'];
function root(omit) {const nodes=new Map(names.filter(x=>x!==omit).map(x=>[x,{textContent:''}]));return {nodes,querySelector:s=>nodes.get(s.match(/"([^"]+)"/)?.[1])??null};}
test('host wiring requires explicit authorized demo context',()=>assert.throws(()=>connectFilesystemDemo(root()),/AUTHORIZED_DEMO_CONTEXT_REQUIRED/));
test('host wiring rejects missing DOM slots instead of partially displaying a status',()=>assert.throws(()=>connectFilesystemDemo(root('effects'),{authorized:true}),/MISSING_FS_V28_SLOT:effects/));
test('authorized mount starts fail-closed with no claimed approval or resolution',()=>{const r=root();const handle=connectFilesystemDemo(r,{authorized:true});assert.equal(r.nodes.get('availability').textContent,'UNAVAILABLE');assert.equal(r.nodes.get('approval').textContent,'NOT_ATTESTED');assert.equal(r.nodes.get('resolution').textContent,'NOT_ATTESTED');assert.equal(r.nodes.get('mode').textContent,'SYNTHETIC');assert.equal(r.nodes.get('effects').textContent,'NO_LIVE_EFFECTS');handle.dispose();});
