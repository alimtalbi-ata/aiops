#!/usr/bin/env python3
"""FS1072: resilient browser diagnostic, including SVG nodes, using existing venv."""
import datetime,json,os,pathlib
from playwright.sync_api import sync_playwright
base="http://127.0.0.1:7777"
out=pathlib.Path.home()/".local/state/aiops-debian-agent/portal-playwright"/("fs1072-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
out.mkdir(parents=True,mode=0o700,exist_ok=False)
os.chmod(out,0o700)
print("FS1072_DIAG_DIR="+str(out),flush=True)
events={"page_errors":[],"console_errors":[],"api_responses":[],"request_failures":[]}
report={"http":None,"dom":{},"events":events,"diagnostic_errors":[]}
def clean(s):
 s=str(s).replace(base,"LOCAL_PORTAL")
 return s[:220]
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path="/usr/bin/chromium",args=["--no-sandbox","--disable-dev-shm-usage"])
  try:
   page=browser.new_page(viewport={"width":1440,"height":900})
   page.on("pageerror",lambda e:events["page_errors"].append(clean(e)))
   page.on("console",lambda m:events["console_errors"].append(clean(m.text)) if m.type=="error" else None)
   page.on("response",lambda r:events["api_responses"].append({"path":r.url.split("?")[0].replace(base,""),"status":r.status}) if r.url.startswith(base+"/api/fs1051/") else None)
   page.on("requestfailed",lambda r:events["request_failures"].append({"path":r.url.split("?")[0].replace(base,""),"error":clean(r.failure)}) if r.url.startswith(base) else None)
   response=page.goto(base+"/explorer/visual",wait_until="domcontentloaded",timeout=20000)
   report["http"]=response.status if response else None
   print("FS1072_HTTP="+str(report["http"]),flush=True)
   page.wait_for_timeout(7000)
   # textContent works for HTML and SVG and does not require HTMLElement.
   report["dom"]=page.evaluate("""() => {
     const ids=['up','down','nodes','edges','graph','targets','search','refresh','detail'];
     const result={};
     for(const id of ids){
       const el=document.getElementById(id);
       result[id]={exists:!!el,tag:el?.tagName||null,text:(el?.textContent||'').trim().slice(0,120),
         children:el?.children?.length||0};
     }
     result.graph_node_count=document.querySelectorAll('#graph .node').length;
     result.targets_row_count=document.querySelectorAll('#targets tr').length;
     return result;
   }""")
   print("FS1072_DOM="+json.dumps(report["dom"],ensure_ascii=False),flush=True)
   print("FS1072_EVENTS="+json.dumps(events,ensure_ascii=False),flush=True)
   page.screenshot(path=str(out/"portal-visual-diagnostic.png"),full_page=True,timeout=15000)
   print("FS1072_SCREENSHOT=PASS",flush=True)
  finally:browser.close()
except Exception as exc:
 report["diagnostic_errors"].append(clean(type(exc).__name__+": "+str(exc)))
 print("FS1072_DIAGNOSTIC_ERROR="+report["diagnostic_errors"][-1],flush=True)
finally:
 path=out/"fs1072-diagnostic.json"
 path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 os.chmod(path,0o600)
 print("FS1072_REPORT="+str(path),flush=True)
 print("FS1072_RESULT="+("COMPLETE" if not report["diagnostic_errors"] else "PARTIAL"),flush=True)
