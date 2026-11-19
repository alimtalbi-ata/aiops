const {test,expect}=require('../../../qa/mission-control/node_modules/@playwright/test');
test.use({trace:'off',screenshot:'off',video:'off',serviceWorkers:'block'});
test('P0 isolated POC nine-view functional smoke',async({page},info)=>{
 test.skip(info.project.name!=='chromium','P0 desktop only');
 const origin=new URL(process.env.BASE_URL);
 const viewer=process.env.QA_VIEWER_TOKEN;
 if(viewer&&origin.protocol!=='https:'&&!['localhost','127.0.0.1','[::1]'].includes(origin.hostname))throw Error('Secure origin required');
 test.setTimeout(120000);
 let writes=0,phase='SETUP';const statusCounts={};
 const check=expect.configure({timeout:7000});
 await page.context().route('**/*',async route=>{
  const r=route.request();if(!['GET','HEAD','OPTIONS'].includes(r.method())){writes++;return route.abort();}
  if(new URL(r.url()).origin!==origin.origin)return route.abort();
  return route.continue();
 });
 await page.routeWebSocket('**/*',ws=>ws.close());
 page.on('response',r=>{const p=new URL(r.url());if(p.origin===origin.origin&&p.pathname.startsWith('/api/mission-data/'))statusCounts[r.status()]=(statusCounts[r.status()]||0)+1;});
 try{
  await page.goto(process.env.UI_PATH||'/mission-control');
  const nav=page.getByRole('navigation',{name:'Navigation'});
  const buttons=nav.getByRole('button');await check(buttons).toHaveCount(9);
  const mode=page.locator('select:has(option[value="demo"]):has(option[value="operational"])');
  await check(mode).toHaveCount(1);await mode.selectOption('operational');
  phase='BEFORE_VIEWER';await check(nav).toBeVisible();
  if(viewer){
   phase='VIEWER';await page.getByText('Accès viewer / DEMO',{exact:true}).click();
   await page.getByLabel('Viewer',{exact:true}).fill(viewer);
   await page.getByRole('button',{name:'Appliquer en mémoire'}).click();
  }
  for(const m of ['operational','demo']){
   await mode.selectOption(m);await check(mode).toHaveValue(m);
   for(let i=0;i<9;i++){
    phase=m+'_VIEW_'+(i+1);
    await buttons.nth(i).click();
    await check(page.getByRole('heading',{level:1})).toBeVisible();
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1);
    console.log('POC_SCREEN '+phase+' visible=true overflow='+overflow);
   }
   if(m==='demo'){
    phase='DEMO_TWIN';await nav.getByRole('button',{name:'Digital Twin',exact:true}).click();
    await check(page.locator('svg[aria-label="Topologie des dépendances"]')).toBeVisible();
    phase='DEMO_SYNTHETIC';await check(page.getByText(/DONNÉES SYNTHÉTIQUES/).first()).toBeVisible();
   }
  }
  phase='RETURN';await mode.selectOption('operational');await check(mode).toHaveValue('operational');
  expect(writes).toBe(0);
 }catch{throw Error('P0 smoke failed at '+phase);}
 finally{console.log('POC_API_STATUS_COUNTS '+JSON.stringify(statusCounts));console.log('POC_BLOCKED_WRITES '+writes);}
});
