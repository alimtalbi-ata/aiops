const {test,expect}=require('../../../qa/mission-control/node_modules/@playwright/test');
test.use({trace:'off',screenshot:'off',video:'off',serviceWorkers:'block'});
test('RAG connected citations, filter and denied read',async({page},info)=>{
 test.skip(info.project.name!=='chromium','Desktop P0');
 test.setTimeout(90000);
 const origin=new URL(process.env.BASE_URL);let writes=0,phase='SETUP',deny=false;
 const check=expect.configure({timeout:10000});
 await page.context().route('**/*',async route=>{
 const r=route.request(),u=new URL(r.url());
 if(!['GET','HEAD','OPTIONS'].includes(r.method())){writes++;return route.abort();}
 if(u.origin!==origin.origin)return route.abort();
 if(deny&&u.pathname==='/api/mission-actions/rag')return route.fulfill({status:403,contentType:'application/json',body:'{}'});
 return route.continue();
 });
 await page.context().routeWebSocket('**/*',ws=>ws.close());
 try{
 await page.goto(process.env.UI_PATH||'/mission-control');
 const nav=page.getByRole('navigation',{name:'Navigation'});
 const pending=page.waitForResponse(r=>new URL(r.url()).origin===origin.origin&&new URL(r.url()).pathname==='/api/mission-actions/rag'&&r.request().method()==='GET');
 phase='RAG_READ';await nav.getByRole('button',{name:'Intelligence',exact:true}).click();
 const res=await pending;expect(res.status()).toBe(200);
 const asset=new URL(res.url()).searchParams.get('asset');
 const payload=await res.json();
 expect(asset).toBe('brocade-fc01');expect(payload.asset).toBe(asset);
 expect(payload.schema).toBe('aiops.noc-demo-rag-drilldown.v1');
 expect(payload.state).toBe('SYNTHETIC_REFERENCE_ONLY');
 expect(payload.llm_inference_performed).toBe(false);
 expect(payload.source_runtime_observed).toBe(false);
 expect(payload.live_remediation_authorized).toBe(false);
 expect(payload.catalog_sha256).toMatch(/^[a-f0-9]{64}$/);
 expect(payload.citations.length).toBeGreaterThan(0);
 const panel=page.getByRole('region',{name:'Recherche RAG connectée'});
 await check(panel.getByRole('status')).toHaveText('Références synthétiques disponibles');
 const articles=panel.getByRole('article');
 await check(articles).toHaveCount(payload.citations.length);
 for(const c of payload.citations){
 expect(c.asset).toBe(asset);expect(c.doc_sha256).toMatch(/^[a-f0-9]{64}$/);
 const article=articles.filter({has:page.getByRole('heading',{name:c.doc_id,exact:true})});
 await check(article).toHaveCount(1);
 await check(article.getByText(c.sample,{exact:false})).toBeVisible();
 await article.getByText('Empreinte de la référence',{exact:true}).click();
 await check(article.locator('code')).toHaveText(c.doc_sha256);
 }
 phase='FILTER';const filter=panel.getByLabel('Filtrer les références');
 await filter.fill('qa-no-match-17b30a');await check(articles).toHaveCount(0);
 await filter.fill('');await check(articles).toHaveCount(payload.citations.length);
 phase='DENIAL_MOCK';deny=true;
 await page.getByRole('button',{name:'Actualiser le contexte'}).click();
 await check(panel.getByRole('status')).toHaveText('UNKNOWN — aucune référence qualifiée');
 await check(articles).toHaveCount(0);expect(writes).toBe(0);
 }catch{throw Error('POC RAG failed at '+phase);}
 finally{console.log('POC_BLOCKED_WRITES '+writes);}
});
