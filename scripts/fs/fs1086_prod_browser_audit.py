#!/usr/bin/env python3
"""Read-only browser audit of deployed production dashboard."""
import datetime,json,os,pathlib,sys
from playwright.sync_api import sync_playwright
base="http://127.0.0.1:7777"
out=pathlib.Path.home()/".local/state/aiops-debian-agent/portal-playwright"/("fs1086-prod-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
out.mkdir(mode=0o700,parents=True,exist_ok=False)
os.chmod(out,0o700)
report={"status":"FAIL","metrics":{},"checks":{},"console":[],"http_errors":[]}
print("FS1086_CAPTURE_DIR="+str(out),flush=True)
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path="/usr/bin/chromium",args=["--no-sandbox","--disable-dev-shm-usage"])
  try:
   page=browser.new_page(viewport={"width":1440,"height":900})
   console=[]
   api=[]
   http_errors=[]
   network_errors=[]
   page.on("console",lambda m:console.append({"text":m.text[:250],"url":m.location.get("url","")}) if m.type=="error" else None)
   page.on("pageerror",lambda e:network_errors.append("JS: "+str(e)[:250]))
   page.on("requestfailed",lambda r:network_errors.append("REQUEST: "+r.url.replace(base,"")[:150]))
   page.on("response",lambda r:api.append([r.url.replace(base,"").split("?")[0],r.status]) if r.url.startswith(base+"/api/fs1051/") else None)
   page.on("response",lambda r:http_errors.append([r.url.replace(base,"").split("?")[0],r.status]) if r.status>=400 else None)
   response=page.goto(base+"/explorer/visual",wait_until="domcontentloaded",timeout=20000)
   assert response and response.status==200,"visual HTTP not 200"
   csp=response.headers.get("content-security-policy","")
   assert csp.count("sha256-")>=2 and "connect-src 'self'" in csp,"effective CSP missing hashes"
   print("FS1086_HTTP=200 CSP_HASHES=PASS",flush=True)
   page.wait_for_function("""() => ['up','down','nodes','edges'].every(id => /^\\d+$/.test(document.getElementById(id)?.textContent?.trim() || ''))""",timeout=25000)
   metrics={k:int(page.locator("#"+k).text_content()) for k in ("up","down","nodes","edges")}
   report["metrics"]=metrics
   print("FS1086_METRICS="+json.dumps(metrics),flush=True)
   rows=page.locator("#targets tr").count()
   graph=page.locator("#graph .node").count()
   assert rows>0 and graph>0,"table or graph empty"
   print("FS1086_TARGET_ROWS="+str(rows)+" GRAPH_NODES="+str(graph),flush=True)
   page.screenshot(path=str(out/"portal-7777-desktop.png"),full_page=True)
   print("FS1086_DESKTOP=PASS",flush=True)
   page.locator("#graph .node circle").first.click(timeout=7000)
   assert page.locator("#detail").text_content().strip()!="Sélectionnez un nœud","node selection failed"
   report["checks"]["node_selection"]="PASS"
   page.locator("#search").fill("FS1086_UNMATCHABLE_7a2f")
   assert page.locator("#graph .node").count()==0,"search filter failed"
   page.locator("#search").fill("")
   assert page.locator("#graph .node").count()>0,"search reset failed"
   report["checks"]["search"]="PASS"
   page.locator("#refresh").click()
   page.wait_for_function("""() => /^\\d+$/.test(document.getElementById('up')?.textContent?.trim() || '')""",timeout=15000)
   report["checks"]["refresh"]="PASS"
   page.set_viewport_size({"width":390,"height":844})
   page.screenshot(path=str(out/"portal-7777-mobile.png"),full_page=True)
   print("FS1086_MOBILE=PASS",flush=True)
   report["console"]=console
   report["http_errors"]=http_errors
   print("FS1086_API="+json.dumps(api),flush=True)
   print("FS1086_HTTP_ERRORS="+json.dumps(http_errors),flush=True)
   print("FS1086_CONSOLE="+json.dumps(console),flush=True)
   assert len([x for x in api if x[1]==200])>=2,"missing API 200"
   assert not [x for x in http_errors if x[0]!="/favicon.ico"],"HTTP errors outside favicon"
   assert not network_errors,"network/JS errors: "+repr(network_errors)
   other=[x for x in console if not (x["url"]==base+"/favicon.ico" and x["text"]=="Failed to load resource: the server responded with a status of 404 (Not Found)")]
   assert not other,"nonfavicon console errors: "+repr(other)
   report["status"]="PASS"
  finally:browser.close()
except Exception as e:
 print("FS1086_ERROR="+type(e).__name__+": "+str(e)[:450],flush=True)
 report["error"]=type(e).__name__+": "+str(e)[:450]
finally:
 dest=out/"fs1086-report.json"
 dest.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
 os.chmod(dest,0o600)
 print("FS1086_REPORT="+str(dest),flush=True)
 print("FS1086_RESULT="+report["status"],flush=True)
if report["status"]!="PASS":sys.exit(1)
