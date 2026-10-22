"""Full controls for the public V2.13.11 STAR storyboard via Playwright Chromium.
Tests operate on a locally-served artifact or an explicitly supplied URL; no AIOps stack mutations.
Usage: python tests/browser/qualify_v21311_star.py --url http://127.0.0.1:8000/app/portal/public_demo_assets/AIOPS-EXECUTIVE-THEATER-PUBLIC.html
"""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--url",required=True)
    parser.add_argument("--output",default="v21311-chromium.json")
    args=parser.parse_args()
    errors=[]
    checks={}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        page=browser.new_page(viewport={"width":1440,"height":900})
        page.on("pageerror",lambda err:errors.append(str(err)))
        r=page.goto(args.url,wait_until="load")
        checks["loaded"]=bool(r and r.status==200)
        checks["twelve_steps"]=page.locator('nav[aria-label="Choisir une scène"] button').count()==12
        checks["initial"]=page.locator("#counter").inner_text()=="1 / 12"
        page.locator("#next").click()
        checks["next"]=page.locator("#counter").inner_text()=="2 / 12"
        page.locator("#prev").click()
        checks["previous"]=page.locator("#counter").inner_text()=="1 / 12"
        page.locator('nav button[aria-label^="Étape 12"]').click()
        checks["direct_step"]=page.locator("#counter").inner_text()=="12 / 12"
        page.locator("#reset").click()
        checks["reset"]=page.locator("#counter").inner_text()=="1 / 12"
        page.locator("#toggle").click()
        checks["pause_label"]=page.locator("#toggle").inner_text().strip()=="⏸ Pause"
        page.locator("#toggle").click()
        checks["resume_label"]=page.locator("#toggle").inner_text().strip()=="▶ Lecture"
        page.evaluate("document.activeElement.blur()")
        page.keyboard.press("ArrowRight")
        checks["keyboard"]=page.locator("#counter").inner_text()=="2 / 12"
        checks["provenance"]=page.get_by_text("SIMULATED_TARGET").count()>0
        checks["no_console_errors"]=not errors
        page.screenshot(path=str(Path(args.output).with_suffix(".png")),full_page=True)
        browser.close()
    result={"scope":"V21311_INTERACTION_TEST","checks":checks,"passed":all(checks.values()),"errors":errors,
            "limits":"No DGX, Core execution, LIVE remediation or historical access qualification."}
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result["passed"] else 1)
if __name__=="__main__": main()
