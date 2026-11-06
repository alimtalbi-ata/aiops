#!/usr/bin/env python3
"""FS1071: read-only browser diagnostic; never save cookies or response bodies."""
import datetime,json,os,pathlib
from playwright.sync_api import sync_playwright
base="http://127.0.0.1:7777"
out=pathlib.Path.home()/".local/state/aiops-debian-agent/portal-playwright"/("fs1071-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
out.mkdir(parents=True,mode=0o700,exist_ok=False)
os.chmod(out,0o700)
print("FS1071_DIAG_DIR="+str(out),flush=True)
events={"page_errors":[],"console_errors":[],"api_responses":[],"request_failures":[]}
def safe_error(s):return str(s).replace(base,"LOCAL_PORTAL")[:220]
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path="/usr/bin/chromium",args=["--no-sandbox","--disable-dev-shm-usage"])
 try:
  page=browser.new_page(viewport={"width":1440,"height":900})
  page.on("pageerror",lambda e:events["page_errors"].append(safe_error(e)))
  page.on("console",lambda m:events["console_errors"].append(safe_error(m.text)) if m.type=="error" else None)
  page.on("response",lambda r:events["api_responses"].append({"path":r.url.split("?")[0].replace(base,""),"status":r.status}) if r.url.startswith(base+"/api/fs1051/") else None)
  page.on("requestfailed",lambda r:events["request_failures"].append({"path":r.url.split("?")[0].replace(base,""),"error":safe_error(r.failure)}) if r.url.startswith(base) else None)
  r=page.goto(base+"/explorer/visual",wait_until="domcontentloaded",timeout=20000)
  print("FS1071_HTTP="+str(r.status if r else "NONE"),flush=True)
  page.wait_for_timeout(9000)
  ids=("up","down","nodes","edges","graph","targets","search","refresh","detail")
  dom={}
  for key in ids:
   loc=page.locator("#"+key)
   dom[key]={"count":loc.count(),"text":loc.first.inner_text(timeout=1500)[:100] if loc.count() else None}
  print("FS1071_DOM="+json.dumps(dom,ensure_ascii=False),flush=True)
  print("FS1071_EVENTS="+json.dumps(events,ensure_ascii=False),flush=True)
  page.screenshot(path=str(out/"portal-visual-failure.png"),full_page=True)
  print("FS1071_SCREENSHOT=PASS",flush=True)
  # Save sanitized evidence, not response bodies, cookies, headers or secrets.
  report={"dom":dom,"events":events,"http":r.status if r else None}
  target=out/"fs1071-diagnostic.json"
  target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
  os.chmod(target,0o600)
  print("FS1071_RESULT=COMPLETE",flush=True)
 finally:browser.close()
