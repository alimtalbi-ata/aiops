const {test,expect}=require('../../../qa/mission-control/node_modules/@playwright/test');
test.use({trace:'off',screenshot:'off',video:'off',serviceWorkers:'block'});
test('POC Copilot slot and local runbook',async({page},info)=>{
 test.skip(info.project.name!=='chromium','Desktop P0');
 const origin=new URL(process.env.BASE_URL);let writes=0,phase='SETUP';
 const check=expect.configure({timeout:7000});
 await page.context().route('**/*',async route=>{
 const req=route.request();
 if(!['GET','HEAD','OPTIONS'].includes(req.method())){writes++;return route.abort();}
 if(new URL(req.url()).origin!==origin.origin)return route.abort();
 return route.continue();
 });
 await page.context().routeWebSocket('**/*',ws=>ws.close());
 try{
 await page.goto(process.env.UI_PATH||'/mission-control');
 phase='SLOT';await page.getByRole('navigation',{name:'Navigation'}).getByRole('button',{name:'Intelligence',exact:true}).click();
 const panel=page.getByRole('region',{name:'Copilot POC synthétique'});
 await check(panel).toBeVisible();
 const scenario=panel.getByLabel('Scénario');
 const question=panel.getByLabel('Question Copilot');
 const answer=panel.getByRole('status');
 phase='PAYMENTS';await scenario.selectOption('0');await question.selectOption('diagnostic');
 await panel.getByRole('button',{name:'Consulter la réponse synthétique'}).click();
 await check(answer).toHaveText('Saturation du pool de connexions');
 phase='STORAGE';await scenario.selectOption('1');await check(answer).toBeEmpty();
 await panel.getByRole('button',{name:'Consulter la réponse synthétique'}).click();
 await check(answer).toHaveText('Croissance des fichiers temporaires');
 phase='RISK';await question.selectOption('risk');await check(answer).toBeEmpty();
 await panel.getByRole('button',{name:'Consulter la réponse synthétique'}).click();
 await check(answer).toContainText('DENY_LIVE_ACTION');
 phase='RUNBOOK';await panel.getByRole('button',{name:'Avancer la répétition locale'}).click();
 await check(panel.getByText(/Progression locale : 1\/3/)).toBeVisible();
 await panel.getByRole('button',{name:'Réinitialiser'}).click();
 await check(panel.getByText(/Progression locale : 0\/3/)).toBeVisible();
 await check(panel.getByText(/Preuve runtime : MISSING/)).toBeVisible();
 await check(panel.getByText(/Rétablissement réel : UNKNOWN/)).toBeVisible();
 expect(writes).toBe(0);
 }catch{throw Error('POC intelligence failed at '+phase+'; SLOT absence requires composition review');}
 finally{console.log('POC_BLOCKED_WRITES '+writes);}
});
