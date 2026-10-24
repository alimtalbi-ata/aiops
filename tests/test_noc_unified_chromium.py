"""Exercise both NOC srcdoc panes in actual isolated Chromium."""
import asyncio
import json
import hashlib
import os
import unittest
from pathlib import Path
from demo.star_png_integrity import inspect_png
from demo.noc_unified_offline import render_unified_noc

CAT = Path(__file__).resolve().parents[1]/"demo/rag_ops_fixture_catalog.json"
H={"schema":"aiops-checkmk-offline-readonly-v1","provenance":"OPERATOR_EXPORT_UNVERIFIED",
   "runtime_authenticated":False,"live_remediation_authorized":False,
   "captured_at":"2026-10-24T20:00:00Z","age_seconds":60.0,
   "hosts":{"brocade-fc01":{"state":"OK","output":"up"}}}
S={"schema":"aiops-checkmk-services-loopback-v1","provenance":"LOOPBACK_UNVERIFIED",
   "runtime_authenticated":False,"live_remediation_authorized":False,
   "captured_at":"2026-10-24T20:00:00Z","age_seconds":60.0,
   "services":[{"host":"brocade-fc01","description":"FC port","state":"CRIT","output":"down"}]}

class UnifiedBrowserTest(unittest.TestCase):
    def test_actual_chromium_renders_both_noc_views(self):
        from playwright.async_api import async_playwright
        page_html=render_unified_noc(json.loads(CAT.read_text(encoding="utf-8")),H,S)
        async def run():
            async with async_playwright() as engine:
                browser=await engine.chromium.launch(headless=True)
                try:
                    context=await browser.new_context(service_workers="block",accept_downloads=False)
                    await context.route("**/*",lambda route:route.abort())
                    page=await context.new_page()
                    await page.set_content(page_html,wait_until="load",timeout=15000)
                    frames=page.locator("iframe")
                    self.assertEqual(await frames.count(),2)
                    self.assertTrue(await frames.nth(0).content_frame.locator("text=ACME Payments").count()>0)
                    self.assertTrue(await frames.nth(1).content_frame.locator("text=FC port").count()>0)
                    self.assertTrue(await page.locator("text=MODE HORS LIGNE").count()>0)
                    evidence_root=os.environ.get("AIOPS_NOC_BROWSER_EVIDENCE_DIR")
                    if evidence_root:
                        output=Path(evidence_root)
                        output.mkdir(parents=True,exist_ok=True)
                        captured=[]
                        for name,frame in (("unified",page),("synthetic",frames.nth(0)),("checkmk-export",frames.nth(1))):
                            file=output/(name+".png")
                            await frame.screenshot(path=str(file),timeout=15000)
                            digest,size=inspect_png(file)
                            self.assertGreater(size,100)
                            captured.append({"file":file.name,"sha256":digest,"size_bytes":size,
                                             "evidence_type":"LOCAL_OFFLINE_BROWSER_RENDER",
                                             "runtime_authenticated":False})
                        manifest={"schema":"aiops-noc-offline-browser-artifacts-v1","captures":captured,
                                  "source":"SYNTHETIC_AND_UNVERIFIED_EXPORTS",
                                  "runtime_proof_count":0,"live_remediation_authorized":False}
                        (output/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\\n",encoding="utf-8")
                finally:
                    await browser.close()
        asyncio.run(run())
if __name__=="__main__":unittest.main()
