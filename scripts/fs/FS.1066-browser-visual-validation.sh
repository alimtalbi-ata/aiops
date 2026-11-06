#!/usr/bin/env bash
set -euo pipefail
echo "FS1066_MODE=READ_ONLY_BROWSER_VALIDATION"
python3 - <<'PY'
import importlib.util,shutil
pw=importlib.util.find_spec("playwright")
browser=next((p for n in ("chromium","chromium-browser","google-chrome","firefox") if (p:=shutil.which(n))),None)
print("FS1066_PLAYWRIGHT_PYTHON="+("AVAILABLE" if pw else "MISSING"),flush=True)
print("FS1066_SYSTEM_BROWSER="+("AVAILABLE" if browser else "MISSING"),flush=True)
if not pw:
 print("FS1066_BROWSER_VALIDATION=SKIPPED_NO_PLAYWRIGHT",flush=True)
 print("FS1066_RESULT=INCOMPLETE",flush=True)
 raise SystemExit(0)
from playwright.sync_api import sync_playwright
try:
 with sync_playwright() as p:
  browser_obj=None
  try:
   browser_obj=p.chromium.launch(headless=True,args=["--no-sandbox"])
  except Exception as exc:
   if browser and "chrom" in browser:
    try: browser_obj=p.chromium.launch(headless=True,executable_path=browser,args=["--no-sandbox"])
    except Exception: pass
   if browser_obj is None:
    print("FS1066_BROWSER_VALIDATION=SKIPPED_BROWSER_LAUNCH_FAILED",flush=True)
    print("FS1066_RESULT=INCOMPLETE",flush=True)
    raise SystemExit(0)
  try:
   page=browser_obj.new_page(viewport={"width":1440,"height":900})
   errors=[]
   page.on("pageerror",lambda exc: errors.append(str(exc)[:200]))
   response=page.goto("http://127.0.0.1:7777/explorer/visual",wait_until="domcontentloaded",timeout=20000)
   assert response and response.status==200,"page HTTP not 200"
   page.wait_for_function("document.querySelector('#up').textContent.trim() !== '—' && document.querySelector('#nodes').textContent.trim() !== '—'",timeout=20000)
   up=page.locator("#up").inner_text()
   down=page.locator("#down").inner_text()
   nodes=page.locator("#nodes").inner_text()
   edges=page.locator("#edges").inner_text()
   assert all(v.isdecimal() for v in (up,down,nodes,edges))
   print("FS1066_METRICS=UP:"+up+" DOWN:"+down+" NODES:"+nodes+" EDGES:"+edges,flush=True)
   assert page.locator("#targets tr").count()>0,"Prometheus table empty"
   assert page.locator("#graph .node").count()>0,"SVG graph empty"
   print("FS1066_SVG_NODES="+str(page.locator("#graph .node").count()),flush=True)
   page.locator("#graph .node").first.click()
   assert page.locator("#detail").inner_text()!="Sélectionnez un nœud","node selection failed"
   print("FS1066_NODE_SELECTION=PASS",flush=True)
   page.locator("#search").fill("FS1066_NO_MATCH_8d81b2")
   assert page.locator("#graph .node").count()==0,"search filtering failed"
   page.locator("#search").fill("")
   assert page.locator("#graph .node").count()>0,"search reset failed"
   print("FS1066_SEARCH=PASS",flush=True)
   page.locator("#refresh").click()
   page.wait_for_function("document.querySelector('#up').textContent.trim() !== '—'",timeout=15000)
   print("FS1066_REFRESH=PASS",flush=True)
   assert not errors,"JavaScript errors: "+repr(errors)
   print("FS1066_JAVASCRIPT_ERRORS=0",flush=True)
   print("FS1066_BROWSER_VALIDATION=PASS",flush=True)
   print("FS1066_RESULT=PASS",flush=True)
  finally:browser_obj.close()
except SystemExit:raise
except Exception as exc:
 print("FS1066_BROWSER_VALIDATION=FAIL "+type(exc).__name__+" "+str(exc)[:250],flush=True)
 raise
PY
