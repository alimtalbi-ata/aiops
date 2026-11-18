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

class PopulatedAudit(unittest.TestCase):
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
            for width in (320,390,768,1440):
                page.set_viewport_size(dict(width=width,height=900))
                page.set_content(html)
                for detail in page.locator("details").all():
                    if not detail.evaluate("e=>e.open"):
                        detail.locator("summary").focus()
                        page.keyboard.press("Space")
                        self.assertTrue(detail.evaluate("e=>e.open"))
                self.assertFalse(page.evaluate("document.documentElement.scrollWidth>innerWidth"))
                self.assertEqual(page.locator("#same-run-history").count(),1)
                page.evaluate("scrollTo(0,0)")
                png=page.screenshot(path=str(out/f"populated-{width}.png"),full_page=True)
                records.append(dict(width=width,sha256=hashlib.sha256(png).hexdigest(),
                    height=page.evaluate("document.documentElement.scrollHeight"),overflow=False))
            browser.close()
        (out/"populated.json").write_text(json.dumps(dict(executed_sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),scope="STORY_OFFLINE",runtime_attested=False,rows=records),indent=2))
