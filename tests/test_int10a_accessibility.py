"""Populated offline render audit; no new server endpoints."""
import hashlib,json,os,subprocess,unittest
from pathlib import Path
from playwright.sync_api import sync_playwright
from portal.acme_impact_read_model import build_acme_impact_read_model, render_acme_impact_html
from portal.acme_incident_cockpit import project_synthetic_incident_cockpit
from portal.acme_incident_cockpit_html import render_synthetic_cockpit_html
from test_acme_historical_journey_offline import fixture, ATTEMPT
from test_int09b_admission_nominal import fixture as golden, call
from test_int09b_preterminal import chain, invoke
from portal.acme_runtime_workbench import render_hitl_inbox

class PopulatedAudit(unittest.TestCase):
    def test_hitl_inbox(self):
        value=call(golden())
        self.assertIn("Proposition déclarée",render_hitl_inbox(value))
        self.assertIn("UNKNOWN",render_hitl_inbox(value))
        self.assertIn("CONTRACT_ONLY",render_hitl_inbox(value))
        for invalid in (None, {}, dict(value,execution_allowed=True), dict(value,qualification="REJECT")):
            self.assertNotIn("CONTRACT_ONLY",render_hitl_inbox(invalid))
            self.assertNotIn("Proposition déclarée",render_hitl_inbox(invalid))
        self.assertNotIn("Proposition déclarée",render_hitl_inbox(dict(value,execution_allowed=True)))
        self.assertNotIn("Proposition déclarée",render_hitl_inbox(dict(value,qualification="REJECT")))

    def test_populated(self):
        out=Path(os.environ["AIOPS_E2E_ARTIFACT_DIR"])
        out.mkdir(parents=True,exist_ok=True)
        model=build_acme_impact_read_model()
        snapshot,rows=fixture(True)
        html=render_synthetic_cockpit_html(project_synthetic_incident_cockpit(model),
            offline_journey=(snapshot,rows,ATTEMPT),offline_admission=call(golden()),
            offline_preterminal=invoke(chain()))
        records=[]
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            page=browser.new_page()
            page.route("**/*",lambda route:route.abort())
            for width, repetition in ((w,r) for w in (320,390,768,1440) for r in (1,2,3)):
                page.close()
                page=browser.new_page()
                page.route("**/*",lambda route:route.abort())
                page.set_viewport_size(dict(width=width,height=900))
                page.set_content(html)
                for detail in page.locator("details").all():
                    if not detail.evaluate("e=>e.open"):
                        detail.locator("summary").focus()
                        page.keyboard.press("Space")
                        self.assertTrue(detail.evaluate("e=>e.open"))
                overflow=page.evaluate("""() => ({
                    width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
                    candidates: [...document.querySelectorAll('main *')]
                        .filter(e => !e.closest('.table-scroll') && e.getBoundingClientRect().right > innerWidth)
                        .slice(0,20).map(e => ({tag:e.tagName, id:e.id, right:e.getBoundingClientRect().right}))
                })""")
                self.assertFalse(page.evaluate("document.documentElement.scrollWidth>innerWidth"), overflow)
                self.assertEqual(page.locator("#same-run-history").count(),1)
                self.assertEqual(page.locator("#hitl-inbox-title").count(),1)
                inbox=page.get_by_role("region",name="HITL Inbox — consultation offline")
                self.assertEqual(inbox.count(),1)
                self.assertEqual(inbox.get_by_role("heading",level=4).count(),1)
                self.assertEqual(inbox.locator("dt").count(),6)
                self.assertEqual(inbox.locator("dd").count(),6)
                self.assertEqual(inbox.locator("button,a,input,select,textarea").count(),0)
                history=page.locator("#same-run-history")
                self.assertEqual(history.get_by_role("list").count(),1)
                self.assertGreater(history.get_by_role("listitem").count(),0)
                summary=history.locator("summary")
                summary.focus()
                page.keyboard.press("Enter")
                self.assertFalse(history.evaluate("e=>e.open"))
                self.assertTrue(summary.evaluate("e=>document.activeElement===e"))
                page.keyboard.press("Space")
                self.assertTrue(history.evaluate("e=>e.open"))
                self.assertTrue(summary.evaluate("e=>document.activeElement===e"))
                ax=page.context.new_cdp_session(page)
                tree=ax.send("Accessibility.getFullAXTree")["nodes"]
                ax.detach()
                exposed=[dict(role=n.get("role",{}).get("value"),name=n.get("name",{}).get("value"))
                         for n in tree if not n.get("ignored")]
                self.assertIn(dict(role="region",name="HITL Inbox — consultation offline"),exposed)
                self.assertTrue(any(n["role"]=="heading" and n["name"]=="HITL Inbox — consultation offline" for n in exposed))
                ax_path=out/f"populated-ax-{width}-{repetition}.json"
                ax_path.write_text(json.dumps(exposed,ensure_ascii=False,indent=2),encoding="utf-8")
                page.evaluate("() => document.fonts.ready")
                metrics_js="""() => {
                    const root=document.documentElement, body=document.body;
                    const rects=[...document.querySelectorAll('body *')]
                        .filter(e=>e.getClientRects().length && getComputedStyle(e).visibility==='visible')
                        .map(e=>e.getBoundingClientRect().bottom+scrollY);
                    return {scrollHeight:root.scrollHeight,bodyScrollHeight:body.scrollHeight,
                        clientHeight:root.clientHeight,innerHeight,innerWidth,scrollY,
                        devicePixelRatio,contentBottom:Math.max(0,...rects),
                        visualHeight:visualViewport.height,visualScale:visualViewport.scale};
                }"""
                # Observe natural settling after keyboard interaction, before resetting scroll.
                trace=[]
                def settle_at_origin():
                    previous=None
                    stable=0
                    for frame in range(180):
                        page.evaluate("() => new Promise(resolve => requestAnimationFrame(resolve))")
                        sample=page.evaluate(metrics_js)
                        focus=page.evaluate("() => ({tag:document.activeElement.tagName,id:document.activeElement.id,text:document.activeElement.textContent.slice(0,120),x:scrollX})")
                        trace.append(dict(frame=frame,metrics=sample,focus=focus))
                        stable=stable+1 if (sample,focus)==previous else 1
                        previous=(sample,focus)
                        if stable>=12:
                            return sample,focus
                    self.fail("layout/scroll/focus did not settle: "+str(trace[-12:]))
                trace_path=out/f"populated-settle-{width}-{repetition}.json"
                try:
                    settle_at_origin()
                    page.evaluate("window.scrollTo({top:0,left:0,behavior:'instant'})")
                    before,focus_before=settle_at_origin()
                    self.assertEqual(before["scrollY"],0)
                    self.assertEqual(focus_before["x"],0)
                    self.assertTrue(summary.evaluate("e=>document.activeElement===e"))
                finally:
                    trace_path.write_text(json.dumps(trace,ensure_ascii=False,indent=2),encoding="utf-8")
                # Diagnose capture-induced reflow without modifying product styles.
                snapshot_js="""() => [...document.querySelectorAll('html,body,body *')].map((e,i) => {
                    const r=e.getBoundingClientRect(), c=getComputedStyle(e);
                    return {i,tag:e.tagName,id:e.id,cls:e.getAttribute('class'),x:r.x,y:r.y,
                        width:r.width,height:r.height,display:c.display,font:c.font,
                        lineHeight:c.lineHeight,margin:c.margin,padding:c.padding,
                        overflow:c.overflow,position:c.position,visibility:c.visibility,
                        open:e.tagName==='DETAILS'?e.open:null};
                })"""
                page.evaluate("""() => {
                    window.__captureEvents=[];
                    const record=kind=>{
                        if(window.__captureEvents.length<256)
                            window.__captureEvents.push({kind,t:performance.now(),w:innerWidth,h:innerHeight,
                                scrollY,rootHeight:document.documentElement.scrollHeight,
                                active:document.activeElement?.tagName});
                    };
                    window.addEventListener('resize',()=>record('window.resize'));
                    visualViewport.addEventListener('resize',()=>record('visual.resize'));
                    window.addEventListener('scroll',()=>record('scroll'));
                    window.addEventListener('focusin',()=>record('focusin'));
                    window.__captureObserver=new ResizeObserver(()=>record('root/body.resize'));
                    window.__captureObserver.observe(document.documentElement);
                    window.__captureObserver.observe(document.body);
                }""")
                elements_before=page.evaluate(snapshot_js)
                capture_path=out/f"populated-capture-{width}-{repetition}.json"
                png=page.screenshot(path=str(out/f"populated-{width}-{repetition}.png"),full_page=True,scale="css")
                after=page.evaluate(metrics_js)
                elements_after=page.evaluate(snapshot_js)
                events=page.evaluate("() => window.__captureEvents")
                changes=[dict(before=a,after=b) for a,b in zip(elements_before,elements_after) if a!=b]
                capture_path.write_text(json.dumps(dict(before=before,after=after,
                    png_width=int.from_bytes(png[16:20],"big"),png_height=int.from_bytes(png[20:24],"big"),
                    elements_before=len(elements_before),elements_after=len(elements_after),
                    changes=changes,events=events),ensure_ascii=False,indent=2),encoding="utf-8")
                self.assertEqual(len(elements_before),len(elements_after))
                self.assertEqual(png[:8],bytes.fromhex("89504e470d0a1a0a"))
                png_width=int.from_bytes(png[16:20],"big")
                png_height=int.from_bytes(png[20:24],"big")
                self.assertEqual(png_width,width)
                self.assertEqual(before,after)
                # Geometric coverage of visible element bounds, not pixel-level inspection.
                self.assertGreaterEqual(png_height+1,before["contentBottom"],(before,after,png_height))
                records.append(dict(width=width,repetition=repetition,sha256=hashlib.sha256(png).hexdigest(),
                    height=after["scrollHeight"],overflow=False,
                    png_width=png_width,png_height=png_height,metrics_before=before,metrics_after=after,
                    png_dom_delta=png_height-after["scrollHeight"],bottom_geometry_covered=True,
                    settle_sha256=hashlib.sha256(trace_path.read_bytes()).hexdigest(),
                    capture_sha256=hashlib.sha256(capture_path.read_bytes()).hexdigest(),
                    ax_sha256=hashlib.sha256(ax_path.read_bytes()).hexdigest(),
                    native_zoom="NOT_TESTED",real_assistive_technology="NOT_TESTED"))
            browser.close()
        (out/"populated.json").write_text(json.dumps(dict(executed_sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),scope="STORY_OFFLINE",runtime_attested=False,rows=records),indent=2))
