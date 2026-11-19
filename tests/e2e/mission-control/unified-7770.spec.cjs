const {test,expect}=require('../../../qa/mission-control/node_modules/@playwright/test');
test.use({trace:'off',screenshot:'off',video:'off',serviceWorkers:'block'});
test('7770 historical surface preservation',async({page},info)=>{
 test.skip(info.project.name!=='chromium','Desktop comparison');
 test.setTimeout(90000);
 const origin=new URL(process.env.BASE_URL);let writes=0,phase='SETUP';
 const check=expect.configure({timeout:7000});
 await page.context().route('**/*',async route=>{
 const r=route.request();
 if(!['GET','HEAD','OPTIONS'].includes(r.method())){writes++;return route.abort();}
 if(new URL(r.url()).origin!==origin.origin)return route.abort();
 return route.continue();
 });
 await page.context().routeWebSocket('**/*',ws=>ws.close());
 try{
 phase='ROOT';const root=await page.goto('/');expect(root.status()).toBe(200);
 const nav=page.locator('header nav');
 for(const href of ['#runs','#twin','#copilot','#noc','#integrations','/itsm','/demo/acme-impact','/demo/explore-story']){
 phase='NAV_'+href;await check(nav.locator('a[href="'+href+'"]')).toBeVisible();
 if(href.startsWith('#')){
 await nav.locator('a[href="'+href+'"]').click();await check(page.locator(href)).toBeVisible();
 }
 console.log('7770_NAV '+href+' PASS');
 }
 for(const [name,selector] of [['Runs','#portal-runs'],['RunDetail','#run-detail-open'],['Twin','#portal-twin'],['Copilot','#q'],['NOC','#noc-result'],['Grafana','#noc-grafana-result'],['RAG','#noc-rag-result'],['Integrations','#portal-navigation-status']]){
 phase=name;await check(page.locator(selector)).toBeVisible();console.log('7770_CONTROL '+name+' PASS');
 }
 for(const width of [1440,390]){
 await page.setViewportSize({width,height:900});
 console.log('7770_OVERFLOW '+width+' '+await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1));
 }
 expect(writes).toBe(0);
 }catch{throw Error('7770 preservation failed at '+phase);}
 finally{console.log('7770_BLOCKED_WRITES '+writes);}
});
