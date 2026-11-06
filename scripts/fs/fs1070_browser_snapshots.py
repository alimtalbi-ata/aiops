#!/usr/bin/env python3
"""FS1070: existing Playwright venv, read-only production visual check."""
import datetime,json,os,pathlib,sys
from playwright.sync_api import sync_playwright

BASE="http://127.0.0.1:7777"
ROOT=pathlib.Path.home()/".local/state/aiops-debian-agent/portal-playwright"
OUT=ROOT/("fs1070-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
OUT.mkdir(mode=0o700,parents=True,exist_ok=False)
os.chmod(OUT,0o700)
print("FS1070_CAPTURE_DIR="+str(OUT),flush=True)
report={"status":"FAIL","url":BASE+"/explorer/visual","checks":{},"errors":[]}
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path="/usr/bin/chromium",args=["--no-sandbox","--disable-dev-shm-usage"])
  try:
   page=browser.new_page(viewport={"width":1440,"height":900},device_scale_factor=1)
   errors=[]
   page.on("pageerror",lambda e:errors.append(str(e)[:300]))
   response=page.goto(BASE+"/explorer/visual",wait_until="domcontentloaded",timeout=25000)
   assert response and response.status==200,"portal HTTP response not 200"
   page.wait_for_function("""() => ['up','down','nodes','edges'].every(id => /^\\d+$/.test(document.getElementById(id)?.textContent?.trim() || ''))""",timeout=25000)
   metrics={key:int(page.locator("#"+key).inner_text()) for key in ("up","down","nodes","edges")}
   report["metrics"]=metrics
   print("FS1070_METRICS="+json.dumps(metrics,sort_keys=True),flush=True)
   assert page.locator("#targets tr").count()>0,"targets table empty"
   count=page.locator("#graph .node").count()
   assert count>0,"SVG nodes absent"
   print("FS1070_GRAPH_NODES="+str(count),flush=True)
   page.screenshot(path=str(OUT/"portal-visual-desktop.png"),full_page=True)
   print("FS1070_DESKTOP_SNAPSHOT=PASS",flush=True)
   page.locator("#graph .node").first.click()
   assert page.locator("#detail").inner_text().strip()!="Sélectionnez un nœud","node detail not updated"
   report["checks"]["node_selection"]="PASS"
   page.locator("#search").fill("FS1070_NO_MATCH_58c2b7")
   assert page.locator("#graph .node").count()==0,"search did not filter"
   page.locator("#search").fill("")
   assert page.locator("#graph .node").count()>0,"search reset failed"
   report["checks"]["search"]="PASS"
   page.locator("#refresh").click()
   page.wait_for_function("""() => /^\\d+$/.test(document.getElementById('up')?.textContent?.trim() || '')""",timeout=15000)
   report["checks"]["refresh"]="PASS"
   page.set_viewport_size({"width":390,"height":844})
   page.screenshot(path=str(OUT/"portal-visual-mobile.png"),full_page=True)
   print("FS1070_MOBILE_SNAPSHOT=PASS",flush=True)
   assert not errors,"JS errors: "+repr(errors)
   report["checks"]["javascript"]="PASS"
   report["checks"]["desktop_snapshot"]="PASS"
   report["checks"]["mobile_snapshot"]="PASS"
   report["status"]="PASS"
   for k,v in report["checks"].items():print("FS1070_"+k.upper()+"="+v,flush=True)
  finally:browser.close()
except Exception as e:
 report["errors"].append(type(e).__name__+": "+str(e)[:500])
 print("FS1070_ERROR="+report["errors"][0],flush=True)
 raise
finally:
 (OUT/"fs1070-result.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
 os.chmod(OUT/"fs1070-result.json",0o600)
 print("FS1070_RESULT="+report["status"],flush=True)
