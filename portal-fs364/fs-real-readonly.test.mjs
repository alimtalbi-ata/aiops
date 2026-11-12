import test from 'node:test';
import assert from 'node:assert/strict';
import {validateProjection,fetchProjection} from './fs-real-readonly.mjs';
const base={mode:'lab147',glpi_ticket_id:147,synthetic:true,no_live_effects:true,
  core:{state:'BLOCKED'},temporal:{state:'UNKNOWN'},policy:{state:'BLOCKED'},
  incident_id:'INC-DEMO-FS-001',run_id:'RUN-4FABD1786F107E51',evidence_id:'EVD-D2069BA816126499'};
test('lab states are readonly and verified',()=>assert.equal(validateProjection(base,'lab147').policy,'BLOCKED'));
for(const change of [{approved:true},{resolved:true},{glpi_ticket_id:146},{synthetic:false},
 {no_live_effects:false},{core:{state:'RESOLVED'}},{run_id:'bad'}])
 test('reject '+JSON.stringify(change),()=>assert.throws(()=>validateProjection({...base,...change},'lab147')));
test('human questions retained only in insufficient mode',()=>{
 assert.deepEqual(validateProjection({...base,mode:'insufficient',questions:['Quelle rétention ?']},'insufficient').questions,['Quelle rétention ?']);
});
test('same-origin GET, no-store and credentials',async()=>{
 const p=await fetchProjection('lab147',async(url,opts)=>{
   assert.equal(url,'/api/portal/fs-real/projection?mode=lab147&ticket_id=147');
   assert.equal(opts.method,'GET');assert.equal(opts.credentials,'same-origin');
   assert.equal(opts.cache,'no-store');
   return {ok:true,headers:{get:()=> 'application/json'},json:async()=>base};
 });assert.equal(p.ticket,147);
});
for(const status of [401,403,503])
 test('fail closed HTTP '+status,async()=>assert.rejects(fetchProjection('lab147',async()=>({ok:false,status})),/UNAVAILABLE/));
test('reject HTML auth redirect',async()=>assert.rejects(fetchProjection('lab147',async()=>({ok:true,headers:{get:()=> 'text/html'}})),/NON_JSON/));

for (const change of [{approved:'true'},{approved:1},{resolved:'false'},
 {resolved:{status:'RESOLVED'}},{questions:'Quelle rétention ?'},
 {questions:[{text:'Autoriser ?'}]},{questions:['x'.repeat(501)]},
 {questions:Array(13).fill('question')}])
 test('reject ambiguous approval/resolution or malformed questions '+JSON.stringify(change).slice(0,80),
  ()=>assert.throws(()=>validateProjection({...base,...change},'lab147')));
test('explicit false approval and resolution are not proof of acceptance',()=>{
 const p=validateProjection({...base,approved:false,resolved:false},'lab147');
 assert.equal(p.policy,'BLOCKED');
 assert.equal(Object.hasOwn(p,'approved'),false);
});

test('reject redirected JSON even with valid-looking projection',async()=> {
 await assert.rejects(fetchProjection('lab147',async()=>({
   ok:true,redirected:true,url:'https://login.invalid/session',
   headers:{get:()=> 'application/json'},json:async()=>base
 })),/UNAVAILABLE_REDIRECT/);
});
test('reject mismatched response URL even when redirected flag is missing',async()=> {
 await assert.rejects(fetchProjection('lab147',async()=>({
   ok:true,url:'https://portal.invalid/auth/callback',
   headers:{get:()=> 'application/json'},json:async()=>base
 })),/UNAVAILABLE_REDIRECT/);
});

test('reject URL containing expected endpoint as a substring', async () => {
  await assert.rejects(fetchProjection('lab147', async () => ({
    ok:true, url:'https://portal.invalid/evil/api/portal/fs-real/projection?mode=lab147&ticket_id=147',
    headers:{get:()=> 'application/json'},json:async()=>base
  })), /UNAVAILABLE_REDIRECT/);
});
test('reject mismatched query parameters', async () => {
  await assert.rejects(fetchProjection('lab147', async () => ({
    ok:true, url:'https://portal.invalid/api/portal/fs-real/projection?mode=insufficient&ticket_id=147',
    headers:{get:()=> 'application/json'},json:async()=>base
  })), /UNAVAILABLE_REDIRECT/);
});
