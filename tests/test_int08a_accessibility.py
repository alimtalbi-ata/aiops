import hashlib,json,os,subprocess,unittest
from pathlib import Path
import test_explore_story_playwright_e2e as historical
from playwright.sync_api import expect

class AccessibilityAudit(unittest.TestCase):
    setUpClass=classmethod(historical.ExploreStoryChromiumE2E.setUpClass.__func__)
    tearDownClass=classmethod(historical.ExploreStoryChromiumE2E.tearDownClass.__func__)
    setUp=historical.ExploreStoryChromiumE2E.setUp
    tearDown=historical.ExploreStoryChromiumE2E.tearDown
    def test_audit(self):
        out=Path(os.environ["AIOPS_E2E_ARTIFACT_DIR"]);out.mkdir(parents=True,exist_ok=True)
        rows=[]
        for width in (320,390,768,1440):
            self.page.set_viewport_size({"width":width,"height":900})
            for name in ("explore-story","acme-impact","acme-incident-cockpit"):
                self.page.goto(self.base+"/demo/"+name)
                if name=="explore-story":
                    self.page.locator("#story-token").fill(historical.VIEWER)
                    self.page.locator("#start").focus()
                    self.page.keyboard.press("Enter")
                    expect(self.page.locator("#story-status")).to_contain_text("PAUSE / EXPLORE")
                for state in ("initial","expanded"):
                    if state=="expanded":
                        for detail in self.page.locator("details").all():
                            if not detail.evaluate("e=>e.open"):
                                detail.locator("summary").focus()
                                self.page.keyboard.press("Space")
                                self.assertTrue(detail.evaluate("e=>e.open"))
                    self.page.evaluate("scrollTo(0,0)")
                    row=dict(width=width,page=name,state=state,height=self.page.evaluate("document.documentElement.scrollHeight"))
                    row["overflow"]=self.page.evaluate("document.documentElement.scrollWidth>innerWidth")
                    self.assertFalse(row["overflow"])
                    png=self.page.screenshot(path=str(out/f"{width}-{name}-{state}.png"),full_page=True,animations="disabled")
                    row["sha256"]=hashlib.sha256(png).hexdigest()
                    row["keys"]=[]
                    for key in ("Tab","Shift+Tab"):
                        for _ in range(40):
                            self.page.keyboard.press(key)
                            row["keys"].append(self.page.evaluate("""()=>{let e=document.activeElement,s=getComputedStyle(e);return {tag:e.tagName,id:e.id,label:e.getAttribute('aria-label'),outline:s.outline,rect:e.getBoundingClientRect().toJSON()}}"""))
                    row["styles"]=self.page.locator("h1,h2,h3,p,a,th,td,summary,dt,dd,small").evaluate_all("""es=>es.filter(e=>e.getClientRects().length).map(e=>{let s=getComputedStyle(e),p=e;while(p&&getComputedStyle(p).backgroundColor==='rgba(0, 0, 0, 0)')p=p.parentElement;return {tag:e.tagName,color:s.color,background:p?getComputedStyle(p).backgroundColor:null,size:s.fontSize,weight:s.fontWeight}})""")
                    rows.append(row)
        (out/"audit.json").write_text(json.dumps(dict(executed_sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),scope="STORY_OFFLINE",runtime_attested=False,rows=rows),indent=2))
