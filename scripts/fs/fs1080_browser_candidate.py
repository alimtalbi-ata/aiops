#!/usr/bin/env python3
import datetime,json,os,pathlib,sys
from playwright.sync_api import sync_playwright
base="http://127.0.0.1:17877"
out=pathlib.Path.home()/".local/state/aiops-debian-agent/portal-playwright"/("fs1080-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
out.mkdir(mode=0o700,parents=True,exist_ok=False)
os.chmod(out,0o700)
print("FS1080_CAPTURE_DIR="+str(out),flush=True)
report={"status":"FAIL","metrics":{},"checks":{},"errors":[]}
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path="/usr/bin/chromium",args=["--no-sandbox","--disable-dev-shm-usage"])
  try:
   page=browser.new_page(viewport={"width":1440,"height":900})
   errors=[]
   api=[]
   failed_http=[]
   console_details=[]
   failed_requests=[]
   page.on("pageerror",lambda e:errors.append(str(e)[:200]))
   page.on("console",lambda m:(errors.append(m.text[:200]),console_details.append({"text":m.text[:200],"location":m.location,"args":len(m.args)})) if m.type=="error" else None)
   page.on("requestfailed",lambda req:failed_requests.append({"url":req.url.replace(base,""),"failure":req.failure}))
   page.on("response",lambda r:api.append((r.url.split("?")[0].replace(base,""),r.status)) if r.url.startswith(base+"/api/fs1051/") else None)
   page.on("response",lambda r:failed_http.append({"path":r.url.split("?")[0].replace(base,""),"status":r.status}) if r.status>=400 else None)
   response=page.goto(base+"/explorer/visual",wait_until="domcontentloaded",timeout=20000)
   print("FS1080_HTTP="+str(response.status if response else "NONE"),flush=True)
   assert response and response.status==200
   page.wait_for_function("""() => ['up','down','nodes','edges'].every(id => /^\\d+$/.test(document.getElementById(id)?.textContent?.trim() || ''))""",timeout=25000)
   metrics={k:int(page.locator("#"+k).text_content()) for k in ("up","down","nodes","edges")}
   report["metrics"]=metrics
   print("FS1080_METRICS="+json.dumps(metrics),flush=True)
   rows=page.locator("#targets tr").count()
   graph=page.locator("#graph .node").count()
   print("FS1080_TARGET_ROWS="+str(rows)+" GRAPH_NODES="+str(graph),flush=True)
   assert rows>0 and graph>0
   page.screenshot(path=str(out/"portal-visual-desktop.png"),full_page=True)
   print("FS1080_DESKTOP_SNAPSHOT=PASS",flush=True)
   node=page.locator("#graph .node").first
   circle=node.locator("circle")
   geometry=circle.evaluate("(e) => {const r=e.getBoundingClientRect();const x=r.left+r.width/2,y=r.top+r.height/2;const h=document.elementFromPoint(x,y);return {x,y,width:r.width,height:r.height,hitTag:h?.tagName,hitClass:h?.getAttribute('class')}}")
   print("FS1081_NODE_HITTEST="+json.dumps(geometry),flush=True)
   report["checks"]["hit_test"]=geometry
   try:
    circle.click(timeout=4000)
    print("FS1081_POINTER_CLICK=PASS",flush=True)
    report["checks"]["pointer_click"]="PASS"
   except Exception as click_error:
    print("FS1081_POINTER_CLICK=FAIL "+type(click_error).__name__,flush=True)
    report["checks"]["pointer_click"]="FAIL"
   detail=page.locator("#detail")
   if detail.text_content().strip()=="Sélectionnez un nœud":
    node.focus()
    page.keyboard.press("Enter")
    print("FS1081_KEYBOARD_SELECTION=TRIED",flush=True)
   assert detail.text_content().strip()!="Sélectionnez un nœud","SVG selection failed by pointer and keyboard"
   report["checks"]["node_selection"]="PASS"
   page.locator("#search").fill("FS1080_NO_MATCH_7a2f")
   assert page.locator("#graph .node").count()==0
   page.locator("#search").fill("")
   assert page.locator("#graph .node").count()>0
   report["checks"]["search"]="PASS"
   page.locator("#refresh").click()
   page.wait_for_function("""() => /^\\d+$/.test(document.getElementById('up')?.textContent?.trim() || '')""",timeout=15000)
   report["checks"]["refresh"]="PASS"
   page.set_viewport_size({"width":390,"height":844})
   page.screenshot(path=str(out/"portal-visual-mobile.png"),full_page=True)
   print("FS1080_MOBILE_SNAPSHOT=PASS",flush=True)
   print("FS1083_CONSOLE_DETAILS="+json.dumps(console_details),flush=True)
   print("FS1083_REQUEST_FAILURES="+json.dumps(failed_requests),flush=True)
   report["checks"]["console_details"]=console_details
   report["checks"]["request_failures"]=failed_requests
   print("FS1082_HTTP_ERRORS="+json.dumps(failed_http),flush=True)
   print("FS1080_API_RESPONSES="+json.dumps(api),flush=True)
   report["checks"]["http_errors"]=failed_http
   assert len([x for x in api if x[1]==200])>=2
   assert not [x for x in failed_http if x["path"]!="/favicon.ico"],"non-favicon HTTP errors: "+repr(failed_http)
   favicon_console=[x for x in console_details if x["text"]=="Failed to load resource: the server responded with a status of 404 (Not Found)" and x["location"].get("url")==base+"/favicon.ico"]
   other_console=[x for x in console_details if x not in favicon_console]
   assert not other_console,"non-favicon console errors: "+repr(other_console)
   assert not failed_requests,"network failures: "+repr(failed_requests)
   print("FS1084_FAVICON_404_CONSOLE="+str(len(favicon_console)),flush=True)
   print("FS1084_NONFAVICON_CONSOLE_ERRORS="+str(len(other_console)),flush=True)
   print("FS1084_BROWSER_ERRORS=NONE_EXCEPT_CONFIRMED_FAVICON_404",flush=True)
   report["checks"]["browser_errors"]="NONE"
   report["status"]="PASS"
  finally:browser.close()
except Exception as e:
 report["errors"].append(type(e).__name__+": "+str(e)[:400])
 print("FS1080_ERROR="+report["errors"][-1],flush=True)
finally:
 target=out/"fs1080-result.json"
 target.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
 os.chmod(target,0o600)
 print("FS1080_RESULT="+report["status"],flush=True)
if report["status"]!="PASS":sys.exit(1)
