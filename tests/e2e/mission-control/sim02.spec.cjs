const {test,expect}=require('../../../qa/mission-control/node_modules/@playwright/test');
test.use({trace:'off',screenshot:'off',video:'off',serviceWorkers:'block'});
test('SIM02 explicitly authorized single browser simulation',async({page},info)=>{
 test.skip(info.project.name!=='chromium','SIM02 desktop only: one POST per authorized run');
 test.skip(process.env.QA_ENABLE_SIM02!=='1','SIM02 explicit opt-in required');
 if(info.retry!==0||info.repeatEachIndex!==0||info.config.projects.some(p=>p.retries!==0))throw Error('BLOCKED: retries/repeats forbidden');
 const viewer=process.env.QA_VIEWER_TOKEN,operator=process.env.QA_OPERATOR_TOKEN;
 if(!viewer||!operator||viewer===operator)throw Error('BLOCKED: distinct approved credentials required');
 const origin=new URL(process.env.BASE_URL);
 if(origin.protocol!=='https:'&&!['localhost','127.0.0.1','[::1]'].includes(origin.hostname))throw Error('BLOCKED: secure origin required');
 test.setTimeout(120000);page.setDefaultTimeout(7000);
 let phase='SETUP',armed=false,posts=0,blocked=0,j;
 const mark=p=>{phase=p;console.log('QA_SIM02 '+p);};
 const check=expect.configure({timeout:15000});
 await page.context().route('**/*',async route=>{
  const req=route.request(),url=new URL(req.url());
  if(url.origin!==origin.origin){if(!['GET','HEAD','OPTIONS'].includes(req.method()))blocked++;return route.abort();}
  if(['GET','HEAD','OPTIONS'].includes(req.method()))return route.continue();
  if(armed&&posts===0&&req.method()==='POST'&&url.pathname==='/api/mission-actions/demo/simulation'&&!url.search){
   let body;try{body=req.postDataJSON();}catch{}
   if(j&&body&&Object.keys(body).sort().join(',')==='incident_id,run_id,source_sha256'&&body.incident_id===j.incident_id&&body.run_id===j.run_id&&body.source_sha256===j.source_sha256&&req.headers().authorization==='Bearer '+operator){posts++;armed=false;return route.continue();}
  }
  blocked++;return route.abort();
 });
 await page.routeWebSocket('**/*',ws=>ws.close());
 try{
  mark('VIEWER_SETUP');await page.goto(process.env.UI_PATH||'/mission-control');
  const mode=page.locator('select:has(option[value="demo"]):has(option[value="operational"])');
  await check(mode).toHaveCount(1);await mode.selectOption('demo');await check(mode).toHaveValue('demo');
  await page.getByText('Accès viewer / DEMO',{exact:true}).click();
  await page.getByLabel('Viewer',{exact:true}).fill(viewer);
  await page.getByLabel('Opérateur DEMO',{exact:true}).fill(operator);
  const journey=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/mission-actions/journey'&&r.status()===200,{timeout:15000});
  const auth=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/mission-actions/session/operator'&&r.status()===200,{timeout:15000});
  await page.getByRole('button',{name:'Appliquer en mémoire'}).click();
  const [jr,ar]=await Promise.all([journey,auth]);j=await jr.json();const a=await ar.json();
  mark('AUTHORITY');expect(j.mode==='DEMO'&&j.runtime_attested===false&&j.live_remediation_authorized===false&&/^[a-f0-9]{64}$/.test(j.source_sha256)&&a.schema==='aiops.mission-actions.operator-session.v1'&&a.mode==='DEMO'&&a.simulation_authorized===true&&a.tenant_acl_qualified===false&&a.runtime_attested===false&&a.live_remediation_authorized===false).toBe(true);
  const twinBefore=JSON.stringify([j.twin,j.affected_ci_ids,j.affected_cis]);
  const nav=page.getByRole('navigation',{name:'Navigation'});
  await nav.getByRole('button',{name:'Automatisation',exact:true}).click();
  const execution=page.locator('[aria-label="Actions execution"]');
  const simulate=execution.getByRole('button',{name:'Simuler (sans action réelle)'});
  await check(simulate).toBeEnabled();
  mark('ONE_POST');const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/mission-actions/demo/simulation'&&r.request().method()==='POST',{timeout:15000});
  armed=true;await simulate.click();const result=await response;armed=false;
  expect(result.status()).toBe(200);const d=await result.json();
  mark('RECEIPT');expect(d.schema==='aiops.acme-demo-simulation-pipeline.v1'&&d.mode==='DEMO'&&d.incident_id===j.incident_id&&d.run_id===j.run_id&&d.source_sha256===j.source_sha256&&d.actual_recovery_state==='UNKNOWN'&&d.runtime_execution_performed===false&&d.temporal_execution_performed===false&&d.glpi_write_performed===false&&d.live_remediation_authorized===false&&d.evidence_gate?.itil_transition_authorized===false&&d.simulation?.receipt?.simulation_result==='HYPOTHETICAL_ONLY'&&/^[a-f0-9]{64}$/.test(d.simulation?.receipt_sha256)).toBe(true);
  await check(execution.getByRole('status')).toHaveText('SIMULATED');
  const receipt=page.getByRole('region',{name:'Résultat de simulation'});
  await check(receipt.getByText('Effet hypothétique — aucune action réelle')).toBeVisible();
  await check(receipt.getByText('Rétablissement réel : inconnu · Temporal : non exécuté')).toBeVisible();
  await check(receipt.getByText(d.simulation.receipt_sha256,{exact:true})).toBeVisible();
  expect(d.simulation.receipt.runtime_execution_verified===false&&d.simulation.receipt.independent_postcheck_verified===false).toBe(true);
  await check(receipt.locator('.drawer-kpis > div').nth(0)).toContainText('DEGRADED');
  await check(receipt.locator('.drawer-kpis > div').nth(1)).toContainText('HEALTHY');
  mark('EVIDENCE');await nav.getByRole('button',{name:'Evidence',exact:true}).click();
  const evidence=page.locator('[aria-label="Actions evidence"]');
  await evidence.getByRole('button',{name:'Inspecter'}).click();
  await check(evidence.getByText(d.simulation.receipt_sha256,{exact:true})).toBeVisible();
  mark('TWIN_IMMUTABILITY');
  const after=await page.evaluate(async token=>{const r=await fetch('/api/mission-actions/journey',{headers:{Authorization:'Bearer '+token},cache:'no-store',credentials:'omit',redirect:'error'});if(!r.ok)throw Error('journey unavailable');return r.json();},viewer);
  expect(after.source_sha256===j.source_sha256&&after.run_id===j.run_id&&JSON.stringify([after.twin,after.affected_ci_ids,after.affected_cis])===twinBefore).toBe(true);
  mark('OPERATIONAL_RETURN');await mode.selectOption('operational');await check(mode).toHaveValue('operational');
  await check(page.getByText(d.simulation.receipt_sha256,{exact:true})).toHaveCount(0);
  expect(posts===1&&blocked===0).toBe(true);
 }catch{throw Error('SIM02 failed at '+phase+'; no automatic retry; private review required');}
 finally{armed=false;}
});
