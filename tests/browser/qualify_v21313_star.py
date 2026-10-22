"""CSP-safe V2.13.13 browser functional checks, no backend writes."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

def main():
 p=argparse.ArgumentParser();p.add_argument("--url",required=True);p.add_argument("--output",default="v21313-browser.json");a=p.parse_args()
 checks={};errors=[]
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);page=b.new_page(viewport={"width":1280,"height":800})
  page.on("pageerror",lambda e:errors.append(str(e)))
  page.goto(a.url,wait_until="load")
  checks["vector_icons"] = page.locator(".visual svg").count() == 3
  checks["optional_detail"] = page.locator("#more").count() == 1 and page.locator("#more-text").count() == 1
  page.locator("#more summary").click()
  checks["detail_expands"] = page.locator("#more").get_attribute("open") is not None
  checks["scene_focus"] = page.locator("#visual").get_attribute("data-focus") == "0"
  checks["twelve_scenes"]=page.locator("#steps button").count()==12
  checks["business_default"]=page.locator("#lead").inner_text().startswith("Le service critique")
  page.locator("#audience").select_option("technical")
  checks["technical_reading"]=page.locator("#lead").inner_text().startswith("Un symptôme utilisateur")
  page.locator("#evidence-toggle").click()
  checks["evidence_open"]=page.locator("#evidence-panel").is_visible() and page.locator("#evidence-toggle").get_attribute("aria-expanded")=="true"
  checks["provenance"]=page.get_by_text("SIMULATED_TARGET").count()>0 and page.get_by_text("OPERATOR_SUPPLIED_EXPORT").count()>0
  page.locator("#next").click()
  checks["animated_focus_changes"] = page.locator("#visual").get_attribute("data-focus") == "1"
  checks["evidence_changes_with_scene"]="Topologie illustrative" in page.locator("#evidence-detail").inner_text()
  page.locator("#evidence-toggle").click()
  checks["evidence_closed"]=not page.locator("#evidence-panel").is_visible()
  page.locator("#presenter").click()
  checks["presenter"]=not page.locator("aside").is_visible()
  page.locator("#presenter").click()
  page.set_viewport_size({"width":390,"height":844})
  checks["mobile_no_overflow"]=page.locator("body").is_visible() and page.locator("#evidence-toggle").is_visible()
  checks["no_js_errors"]=not errors
  page.screenshot(path=str(Path(a.output).with_suffix(".png")),full_page=True)
  b.close()
 report={"scope":"V21313_BROWSER_FUNCTIONAL","checks":checks,"passed":all(checks.values()),"errors":errors,"limits":"Synthetic narrative UI only; not Core/DGX/LIVE validation"}
 Path(a.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(report,ensure_ascii=False,indent=2))
 raise SystemExit(0 if report["passed"] else 1)
if __name__=="__main__":main()
