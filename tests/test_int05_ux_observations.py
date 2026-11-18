"""INT05 read-only UX observations on the existing ephemeral portal."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest
import test_explore_story_playwright_e2e as historical


class Int05Audit(unittest.TestCase):
    setUpClass = classmethod(historical.ExploreStoryChromiumE2E.setUpClass.__func__)
    tearDownClass = classmethod(historical.ExploreStoryChromiumE2E.tearDownClass.__func__)
    setUp = historical.ExploreStoryChromiumE2E.setUp
    tearDown = historical.ExploreStoryChromiumE2E.tearDown

    def test_observe(self):
        output = Path(os.environ["AIOPS_E2E_ARTIFACT_DIR"])
        output.mkdir(parents=True, exist_ok=True)
        report = {"executed_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(), "scope":"STORY_OFFLINE", "runtime_authenticated":False, "pages":[]}
        for width in (320, 768, 1440):
            for name, path in (("impact","/demo/acme-impact"),("cockpit","/demo/acme-incident-cockpit")):
                self.page.set_viewport_size({"width":width,"height":844 if width==320 else 900})
                self.page.goto(self.base+path)
                row = {"width":width,"page":name,"overflow":self.page.evaluate("document.documentElement.scrollWidth > innerWidth"),"tab":[],"reverse_tab":[],"tables":[]}
                png = self.page.screenshot(path=str(output/f"{width}-{name}.png"),full_page=True,animations="disabled")
                row["sha256"] = hashlib.sha256(png).hexdigest()
                info = """() => {const e=document.activeElement,s=getComputedStyle(e);return {tag:e.tagName,id:e.id,label:e.getAttribute('aria-label'),href:e.getAttribute('href'),outline:s.outlineStyle,outlineColor:s.outlineColor,outlineWidth:s.outlineWidth}}"""
                for key, field in (("Tab","tab"),("Shift+Tab","reverse_tab")):
                    for _ in range(40):
                        self.page.keyboard.press(key)
                        row[field].append(self.page.evaluate(info))
                for region in self.page.locator(".table-scroll").all():
                    region.focus()
                    before=region.evaluate("e=>({left:e.scrollLeft,width:e.clientWidth,extent:e.scrollWidth,label:e.getAttribute('aria-label')})")
                    self.page.keyboard.press("ArrowRight")
                    self.page.wait_for_timeout(200)
                    before["after_right"]=region.evaluate("e=>e.scrollLeft")
                    row["tables"].append(before)
                row["styles"]=self.page.evaluate("""() => Array.from(document.querySelectorAll('h1,h2,h3,p,a,th,td,summary')).filter(e=>e.getClientRects().length).map(e=>{let s=getComputedStyle(e),b=e;while(b && getComputedStyle(b).backgroundColor==='rgba(0, 0, 0, 0)')b=b.parentElement;return {tag:e.tagName,text:e.textContent.trim().slice(0,100),foreground:s.color,background:b?getComputedStyle(b).backgroundColor:null,fontSize:s.fontSize,fontWeight:s.fontWeight}})""")
                row["no_go"]="NO-GO LIVE" in self.page.locator("body").inner_text()
                report["pages"].append(row)
                (output/"observations.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
        self.assertEqual(len(report["pages"]),6)
        self.assertTrue(all(not x["overflow"] and x["no_go"] for x in report["pages"]))
