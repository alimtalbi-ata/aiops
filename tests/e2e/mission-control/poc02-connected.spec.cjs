const {test,expect}=require('../../../qa/mission-control/node_modules/@playwright/test');
test.use({trace:'off',screenshot:'off',video:'off',serviceWorkers:'block'});
test('POC02 connected read-only panels',async({page},info)=>{
 test.skip(info.project.name!=='chromium','Desktop P0');
 test.setTimeout(120000);
 const origin=new URL(process.env.BASE_URL);let writes=0,phase='SETUP';
 const check=expect.configure({timeout:10000});
 await page.context().route('**/*',async route=>{
 const r=route.request();
 if(!['GET','HEAD','OPTIONS'].includes(r.method())){writes++;return route.abort();}
 if(new URL(r.url()).origin!==origin.origin)return route.abort();
 return route.continue();
 });
 await page.context().routeWebSocket('**/*',ws=>ws.close());
 try{
 await page.goto(process.env.UI_PATH||'/mission-control');
 const nav=page.getByRole('navigation',{name:'Navigation'});
 await check(nav.getByRole('button')).toHaveCount(9);
 const tech=page.getByRole('region',{name:'Plateforme technique réelle'});
 phase='SNAPSHOT';await check(tech).toBeVisible();
 await check(tech.getByText(/distinctes du scénario Commerce synthétique/)).toBeVisible();
 for(const state of ['UP','DOWN','UNKNOWN']){
 const metric=tech.locator('.ux-metric').filter({has:page.getByText('Jobs '+state,{exact:true})});
 await check(metric.locator('strong')).toHaveText(/^\d+$/);
 }
 phase='SERVICES';await tech.getByRole('button',{name:'Services techniques'}).click();
 const rows=tech.locator('tbody tr');await check(rows.first()).toBeVisible();
 const values=await rows.locator('td:nth-child(2)').allTextContents();
 for(const state of ['UP','DOWN','UNKNOWN']){
 const metric=tech.locator('.ux-metric').filter({has:page.getByText('Jobs '+state,{exact:true})});
 await check(metric.locator('strong')).toHaveText(String(values.filter(v=>v.trim()===state).length));
 }
 expect(values.every(v=>['UP','DOWN','UNKNOWN'].includes(v.trim()))).toBe(true);
 phase='HISTORY';await tech.getByRole('button',{name:'Historiques techniques'}).click();
 await check(tech.getByRole('heading',{name:'Collecte technique · maximum par job'})).toBeVisible();
 const job=tech.getByLabel('Job technique');
 await check(job).toBeVisible();
 const jobs=await job.locator('option').allTextContents();expect(jobs.length).toBeGreaterThan(0);
 await job.selectOption({label:jobs[0]});
 await check(tech.getByText(/Durée de collecte|Échantillons collectés/).first()).toBeVisible();
 phase='JOURNEY';
 const response=page.waitForResponse(r=>new URL(r.url()).origin===origin.origin&&new URL(r.url()).pathname==='/api/mission-actions/journey'&&r.request().method()==='GET');
 await nav.getByRole('button',{name:'Intelligence',exact:true}).click();
 const panel=page.getByRole('region',{name:'Intelligence connectée DEMO'});
 await check(panel).toBeVisible();
 const res=await response;expect(res.status()).toBe(200);
 const j=await res.json();
 expect(j.schema).toBe('aiops.mission-actions.journey.v1');expect(j.mode).toBe('DEMO');
 expect(j.runtime_attested).toBe(false);expect(j.live_remediation_authorized).toBe(false);
 expect(j.source_sha256).toMatch(/^[a-f0-9]{64}$/);
 await check(panel.getByText('Incident : '+j.incident_id+' · Run : '+j.run_id,{exact:true})).toBeVisible();
 phase='INSPECT';const analyst=panel.getByLabel('Actions analysis');
 await analyst.getByRole('button',{name:'Inspecter',exact:true}).click();
 phase='RAG';const ci=panel.getByLabel('CI',{exact:true});
 await check(ci).toBeVisible();expect(j.affected_ci_ids.length).toBeGreaterThan(0);
 await ci.selectOption(j.affected_ci_ids[0]);
 await panel.getByLabel('Actions ci').getByRole('button',{name:'Inspecter',exact:true}).click();
 await check(panel.getByText(/Rétablissement réel UNKNOWN/)).toBeVisible();
 expect(writes).toBe(0);
 }catch{throw Error('POC02 failed at '+phase);}
 finally{console.log('POC_BLOCKED_WRITES '+writes);}
});
