const {test,expect}=require('../../../qa/mission-control/node_modules/@playwright/test');
test.use({trace:'off',screenshot:'off',video:'off',serviceWorkers:'block'});
test('POC01 autonomous functional smoke',async({page},info)=>{
 test.skip(info.project.name!=='chromium','P0 desktop');
 test.setTimeout(120000);
 const origin=new URL(process.env.BASE_URL);let writes=0,phase='SETUP';
 const check=expect.configure({timeout:7000});
 await page.context().route('**/*',async route=>{
 const r=route.request();
 if(!['GET','HEAD','OPTIONS'].includes(r.method())){writes++;return route.abort();}
 if(new URL(r.url()).origin!==origin.origin)return route.abort();
 return route.continue();
 });
 await page.routeWebSocket('**/*',ws=>ws.close());
 try{
 await page.goto(process.env.UI_PATH||'/mission-control');
 const nav=page.getByRole('navigation',{name:'Navigation'});
 const buttons=nav.getByRole('button');await check(buttons).toHaveCount(9);
 for(const width of [1440,390,320]){
 await page.setViewportSize({width,height:900});
 for(let i=0;i<9;i++){
 phase='VIEW_'+width+'_'+(i+1);
 await buttons.nth(i).click();await check(page.getByRole('heading',{level:1})).toBeVisible();
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1);
 console.log('POC_SCREEN '+phase+' visible=true overflow='+overflow);
 }
 }
 await page.setViewportSize({width:1440,height:900});
 phase='INCIDENT_TWIN';await nav.getByRole('button',{name:'Incidents',exact:true}).click();
 await page.getByRole('button',{name:'Inspecter le CI dans le Twin',exact:true}).click();
 await check(page.locator('svg[aria-label="Topologie des dépendances"]')).toBeVisible();
 await check(page.locator('aside.ux-inspector')).toBeVisible();
 phase='INTELLIGENCE';await nav.getByRole('button',{name:'Intelligence',exact:true}).click();
 await check(page.getByText(/Analyste/).first()).toBeVisible();
 await check(page.getByText(/Critic/).first()).toBeVisible();
 phase='PREVIEW';await nav.getByRole('button',{name:'Automatisation',exact:true}).click();
 await page.getByRole('button',{name:'Afficher le scénario hypothétique',exact:true}).click();
 await check(page.getByRole('status').filter({hasText:'Rétablissement réel UNKNOWN'})).toBeVisible();
 phase='EVIDENCE';await nav.getByRole('button',{name:'Evidence',exact:true}).click();
 await check(page.getByText(/aucun reçu serveur/i).first()).toBeVisible();
 expect(writes).toBe(0);
 }catch{throw Error('POC01 smoke failed at '+phase);}
 finally{console.log('POC_BLOCKED_WRITES '+writes);}
});
