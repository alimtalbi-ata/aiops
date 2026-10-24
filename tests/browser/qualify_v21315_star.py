"""V2.13.15 SAN dual-fabric simulated path behavior, no backend writes."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright
def main():
 p=argparse.ArgumentParser();p.add_argument("--url",required=True);p.add_argument("--output",default="v21315-browser.json");a=p.parse_args()
 checks={};errors=[]
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={"width":1440,"height":900})
  page.on("pageerror",lambda e:errors.append(str(e)))
  page.goto(a.url,wait_until="load")
  checks["initial_nominal"]=page.locator("#san-demo").get_attribute("data-state")=="nominal"
  checks["initial_dual_fabric"]=page.locator("#san-a-label").inner_text()=="Disponible" and page.locator("#san-b-label").inner_text()=="Disponible"
  page.locator("#steps button").nth(1).click()
  checks["degraded_a"]=page.locator("#san-a").get_attribute("data-state")=="degraded" and "Dégradé" in page.locator("#san-a-label").inner_text()
  checks["b_available"]=page.locator("#san-b").get_attribute("data-state")=="nominal"
  checks["no_fabric_measure_claim"]= "pas de mesure réelle" in page.locator("#san-health").inner_text()
  page.locator("#steps button").nth(7).click()
  checks["policy_block_illustrative"]=page.locator("#storyline").get_attribute("data-stage")=="blocked" and page.locator("#san-a").get_attribute("data-state")=="degraded"
  page.locator("#steps button").nth(11).click()
  checks["final_no_false_recovery"]=page.locator("#san-health").inner_text().startswith("Deux chemins illustratifs") and "aucune donnée mesurée" in page.locator("#san-health").inner_text()
  checks["provenance"]=page.get_by_text("SIMULATED_TARGET").count()>0
  page.set_viewport_size({"width":390,"height":844})
  checks["mobile"]=page.locator("#san-demo").is_visible()
  checks["no_js_errors"]=not errors
  page.screenshot(path=str(Path(a.output).with_suffix(".png")),full_page=True)
  browser.close()
 report={"scope":"V21315_SIMULATED_SAN_PATHS","checks":checks,"passed":all(checks.values()),"errors":errors,"limits":"Illustrative dual-fabric only, not live link state, multipathing measurement, DGX output or remediation."}
 Path(a.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(report,ensure_ascii=False,indent=2))
 raise SystemExit(0 if report["passed"] else 1)
if __name__=="__main__":main()
