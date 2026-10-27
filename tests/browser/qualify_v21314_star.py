"""V2.13.14 scene timeline regression; CSP-safe DOM observations."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright

def main():
 p=argparse.ArgumentParser();p.add_argument("--url",required=True);p.add_argument("--output",default="v21314-browser.json");a=p.parse_args()
 checks={};errors=[]
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True)
  page=browser.new_page(viewport={"width":1440,"height":900})
  page.on("pageerror",lambda error:errors.append(str(error)))
  page.goto(a.url,wait_until="load")
  checks["twelve_scenes"]=page.locator("#steps button").count()==12
  checks["initial_signal"]=page.locator("#storyline").get_attribute("data-stage")=="signal"
  page.locator("#steps button").nth(4).click()
  checks["analyst"]=page.locator("#storyline").get_attribute("data-stage")=="analyst" and "non issue" in page.locator("#storyline-status").inner_text()
  page.locator("#steps button").nth(5).click()
  checks["critic"]=page.locator("#storyline").get_attribute("data-stage")=="critic"
  page.locator("#steps button").nth(7).click()
  checks["blocked"]=page.locator("#storyline").get_attribute("data-stage")=="blocked" and "STOP_AUTO" in page.locator("#storyline-status").inner_text()
  page.locator("#steps button").nth(8).click()
  checks["human_review"]=page.locator("#storyline").get_attribute("data-stage")=="review"
  checks["one_active_step"]=page.locator("#storyline-track .current").count()==1
  checks["svg_present"]=page.locator("#visual svg").count()==3
  checks["source_label"]=page.get_by_text("SIMULATED_TARGET").count()>0
  page.set_viewport_size({"width":390,"height":844})
  checks["mobile"]=page.locator("#storyline").is_visible()
  checks["no_js_errors"]=not errors
  page.screenshot(path=str(Path(a.output).with_suffix(".png")),full_page=True)
  browser.close()
 report={"scope":"V21314_SYNTHETIC_TIMELINE","checks":checks,"passed":all(checks.values()),"errors":errors,"limits":"Visual simulation only. No real DGX inference, Policy interposition or LIVE actions."}
 Path(a.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(report,ensure_ascii=False,indent=2))
 raise SystemExit(0 if report["passed"] else 1)
if __name__=="__main__":main()
