const {test,expect}=require('../../../qa/mission-control/node_modules/@playwright/test');
test('runtime anonymous protected GET contracts',async({request})=>{
 for(const path of ['/api/mission-data/health/jobs','/api/mission-data/health/history?minutes=60','/api/mission-data/acme?mode=DEMO','/api/mission-actions/journey']){
 const r=await request.get(path,{maxRedirects:0});expect(r.status(),path).toBe(401);
 }
});
test('runtime FIX01 operator fail closed',async({request})=>{
 const r=await request.get('/api/mission-actions/session/operator',{maxRedirects:0});
 expect(r.status()).toBe(503);expect((await r.json()).detail).toBe('portal_operator_not_configured');expect(r.headers()['cache-control']).toContain('no-store');
});
test('runtime anonymous shell navigation',async({page})=>{
 const errors=[];const failed=[];
 page.on('pageerror',()=>errors.push('pageerror'));
 page.on('response',r=>{if(['script','stylesheet'].includes(r.request().resourceType())&&r.status()>=400)failed.push(r.status())});
 await page.route('**/*',route=>['GET','HEAD','OPTIONS'].includes(route.request().method())?route.continue():route.abort());
 const r=await page.goto(process.env.UI_PATH||'/mission-control');expect(r.status()).toBe(200);
 const nav=page.locator('nav[aria-label="Navigation"]');await expect(nav).toBeVisible();
 const buttons=nav.getByRole('button');await expect(buttons).toHaveCount(9);
 for(let i=0;i<9;i++){await buttons.nth(i).click();await expect(nav).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();}
 expect(errors).toEqual([]);expect(failed).toEqual([]);
});