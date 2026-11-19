const {test,expect}=require('../../../qa/mission-control/node_modules/@playwright/test');
test.use({trace:'off',screenshot:'off',video:'off',serviceWorkers:'block'});
test('runtime ACME browser read-only navigation and viewer isolation',async({page})=>{
 const token=process.env.QA_VIEWER_TOKEN;
 if(!token&&process.env.QA_REQUIRE_VIEWER==='1') throw Error('BLOCKED: approved viewer credential required');
 test.skip(!token,'BLOCKED: approved viewer credential required');
 const origin=new URL(process.env.BASE_URL);
 if(origin.protocol!=='https:'&&!['localhost','127.0.0.1','[::1]'].includes(origin.hostname)) throw Error('Viewer requires HTTPS or loopback');
 if(!/^[!-~]{32,256}$/.test(token)) throw Error('Invalid viewer format');
 const writes=[];
 await page.route('**/*',async route=>{
  const req=route.request();
  if(!['GET','HEAD','OPTIONS'].includes(req.method())){writes.push(req.method());return route.abort();}
  if(new URL(req.url()).origin!==origin.origin)return route.abort();
  return route.continue();
 });
 try{
  await page.goto(process.env.UI_PATH||'/mission-control');
  const nav=page.getByRole('navigation',{name:'Navigation'});
  await expect(nav).toBeVisible();
  const go=async name=>{await nav.getByRole('button',{name,exact:true}).click();await expect(page.getByRole('heading',{level:1,name,exact:true})).toBeVisible();};
  await page.getByLabel('Mode',{exact:true}).selectOption('demo');
  await page.getByText('Accès viewer / DEMO',{exact:true}).click();
  await page.getByLabel('Viewer',{exact:true}).fill(token);
  const acme=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/mission-data/acme'&&r.status()===200);
  const journey=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/mission-actions/journey'&&r.status()===200);
  await page.getByRole('button',{name:'Appliquer en mémoire'}).click();
  const a=(await (await acme).json()).data;const j=await (await journey).json();
  expect(a.source_sha256===j.source_sha256&&j.runtime_attested===false&&j.live_remediation_authorized===false).toBe(true);
  await expect(page.getByText(/DONNÉES SYNTHÉTIQUES/)).toBeVisible();
  await go('Incidents');await expect(page.getByText(j.incident_id,{exact:true})).toBeVisible();
  await go('Digital Twin');const graph=page.locator('svg[aria-label="Topologie des dépendances"]');await expect(graph).toBeVisible();
  await graph.getByRole('button').first().focus();await page.keyboard.press('Enter');await expect(page.locator('aside.ux-inspector')).toBeVisible();await page.keyboard.press('Escape');await expect(page.locator('aside.ux-inspector')).toHaveCount(0);
  await go('Intelligence');await expect(page.getByRole('heading',{name:'Analyste',exact:true})).toBeVisible();await expect(page.getByRole('heading',{name:'Critic',exact:true})).toBeVisible();
  await go('Automatisation');await expect(page.getByRole('button',{name:'Simuler (sans action réelle)'})).toBeDisabled();
  await go('Evidence');await expect(page.getByRole('heading',{name:'Checkpoints synthétiques'})).toBeVisible();await expect(page.getByText(/MISSING/).first()).toBeVisible();
  await go('ITSM');await expect(page.getByRole('link',{name:'Ouvrir ITSM'})).toHaveAttribute('href','/itsm');
  await page.getByLabel('Mode',{exact:true}).selectOption('operational');await go('Incidents');await expect(page.getByText(/Autorité acteur \/ tenant non qualifiée/)).toBeVisible();await expect(page.getByText(j.incident_id,{exact:true})).toHaveCount(0);
  expect(writes).toEqual([]);
 }catch{throw Error('Authenticated browser qualification failed; reproduce privately without publishing credentials or payloads');}
});