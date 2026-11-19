const {test,expect}=require('../../../qa/mission-control/node_modules/@playwright/test');
test.use({trace:'off',screenshot:'off',video:'off',serviceWorkers:'block'});
test('SIM02 mobile read-only authority and responsive inventory',async({page},info)=>{
 test.skip(info.project.name!=='mobile','Mobile only');
 const viewer=process.env.QA_VIEWER_TOKEN,operator=process.env.QA_OPERATOR_TOKEN;
 if(!viewer||!operator||viewer===operator)throw Error('BLOCKED: approved distinct credentials required');
 const origin=new URL(process.env.BASE_URL);
 if(origin.protocol!=='https:'&&!['localhost','127.0.0.1','[::1]'].includes(origin.hostname))throw Error('BLOCKED: secure origin required');
 test.setTimeout(120000);page.setDefaultTimeout(7000);
 const check=expect.configure({timeout:10000});
 let phase='SETUP',blocked=0;
 const mark=p=>{phase=p;console.log('QA_MOBILE '+p);};
 await page.context().route('**/*',async route=>{
  const req=route.request();
  if(!['GET','HEAD','OPTIONS'].includes(req.method())){blocked++;return route.abort();}
  if(new URL(req.url()).origin!==origin.origin)return route.abort();
  return route.continue();
 });
 await page.routeWebSocket('**/*',ws=>ws.close());
 try{
  await page.goto(process.env.UI_PATH||'/mission-control');
  const mode=page.locator('select:has(option[value="demo"]):has(option[value="operational"])');
  await check(mode).toHaveCount(1);await mode.selectOption('demo');
  await page.getByText('Accès viewer / DEMO',{exact:true}).click();
  await page.getByLabel('Viewer',{exact:true}).fill(viewer);
  await page.getByLabel('Opérateur DEMO',{exact:true}).fill(operator);
  mark('AUTHORITY');
  const jwait=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/mission-actions/journey'&&r.status()===200,{timeout:15000});
  const awaiter=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/mission-actions/session/operator'&&r.status()===200,{timeout:15000});
  await page.getByRole('button',{name:'Appliquer en mémoire'}).click();
  const [jr,ar]=await Promise.all([jwait,awaiter]);const j=await jr.json(),a=await ar.json();
  expect(j.mode==='DEMO'&&j.runtime_attested===false&&j.live_remediation_authorized===false&&a.schema==='aiops.mission-actions.operator-session.v1'&&a.mode==='DEMO'&&a.simulation_authorized===true&&a.tenant_acl_qualified===false&&a.runtime_attested===false&&a.live_remediation_authorized===false).toBe(true);
  const nav=page.getByRole('navigation',{name:'Navigation'});
  const buttons=nav.getByRole('button');await check(buttons).toHaveCount(9);
  for(const width of [320,360,390]){
   await page.setViewportSize({width,height:800});
   for(let i=0;i<9;i++){
   mark('WIDTH_'+width+'_VIEW_'+(i+1));await buttons.nth(i).click();
   await check(buttons.nth(i)).toHaveAttribute('aria-current','page');
   await check(page.getByRole('heading',{level:1})).toBeVisible();
   await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth+1)).toBe(true);
   await expect.poll(()=>buttons.nth(i).evaluate(el=>{const r=el.getBoundingClientRect();return r.width>=24&&r.height>=24;})).toBe(true);
   await buttons.nth(i).focus();await check(buttons.nth(i)).toBeFocused();
   }
  }
  mark('SIMULATION_BUTTON_NO_CLICK');await nav.getByRole('button',{name:'Automatisation',exact:true}).click();
  await check(page.locator('[aria-label="Actions execution"]').getByRole('button',{name:'Simuler (sans action réelle)'})).toBeEnabled();
  mark('TWIN');await nav.getByRole('button',{name:'Digital Twin',exact:true}).click();
  await check(page.locator('svg[aria-label="Topologie des dépendances"]')).toBeVisible();
  mark('RETURN');await mode.selectOption('operational');await check(mode).toHaveValue('operational');
  await nav.getByRole('button',{name:'Incidents',exact:true}).click();
  await check(page.getByText(j.incident_id,{exact:true})).toHaveCount(0);
  expect(blocked).toBe(0);
  console.log('QA_MOBILE POST_ALLOWED=0 BLOCKED_WRITES=0');
 }catch{throw Error('Mobile read-only failed at '+phase+'; private review required');}
});
