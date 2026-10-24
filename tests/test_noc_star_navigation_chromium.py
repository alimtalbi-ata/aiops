"""Chromium navigation acceptance for the offline STAR trace."""
import asyncio
import unittest
from demo.noc_star_trace_bundle import make_synthetic_star_events
from demo.noc_star_trace_page import render_noc_star_trace

def fixture_index():
    return {"schema":"aiops-noc-evidence-index-v1",
      "counts":{"OFFLINE_TEST":3,"OBSERVATION":0,"RUNTIME_EVIDENCE":0},
      "runtime_authenticated":False,"live_remediation_authorized":False,
      "entries":[{"id":"noc-offline-"+n,"file":n+".png","sha256":"a"*64,
                  "size_bytes":123,"class":"OFFLINE_TEST",
                  "source":"LOCAL_OFFLINE_BROWSER_RENDER","runtime_authenticated":False,
                  "promotable_to_runtime":False}
                 for n in ("unified","synthetic","checkmk-export")]}

class NocStarNavigationBrowserTests(unittest.TestCase):
    def test_real_chromium_follows_internal_cue_links(self):
        from playwright.async_api import async_playwright
        html=render_noc_star_trace(fixture_index(),make_synthetic_star_events())
        async def exercise():
            async with async_playwright() as playwright:
                browser=await playwright.chromium.launch(headless=True)
                try:
                    context=await browser.new_context(service_workers="block",accept_downloads=False)
                    requests=[]
                    context.on("request",lambda request:requests.append(request.url))
                    await context.route("**/*",lambda route:route.abort())
                    page=await context.new_page()
                    await page.set_content(html,wait_until="load")
                    for cue in ("detect","analyze","verify"):
                        link=page.locator('a[href="#cue-'+cue+'"]').first
                        self.assertTrue(await link.is_visible())
                        await link.click()
                        self.assertEqual(await page.evaluate("location.hash"),"#cue-"+cue)
                        self.assertEqual(await page.locator('#cue-'+cue).count(),1)
                    self.assertEqual(requests,[])
                    self.assertIn("OFFLINE_TEST",await page.locator("body").inner_text())
                finally:
                    await browser.close()
        asyncio.run(exercise())
if __name__=="__main__":unittest.main()
