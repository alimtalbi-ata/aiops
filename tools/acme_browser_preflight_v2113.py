#!/usr/bin/env python3
"""Read-only Chromium interaction preflight for ACME story.
Requires playwright and a preinstalled Chromium browser. Never installs dependencies.
"""
import argparse,json
from datetime import datetime,timezone

def check(url):
    from playwright.sync_api import sync_playwright
    events=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page()
        writes=[]
        page.on("request",lambda req: writes.append({"method":req.method,"url":req.url}) if req.method not in ("GET","HEAD","OPTIONS") else None)
        response=page.goto(url,wait_until="load",timeout=15000)
        assert response and response.status==200,"story HTTP 200 expected"
        assert page.get_by_text("FICTIF / SANS EFFET").count()>0,"simulation label missing"
        next_button=page.locator("#story-next")
        reset_button=page.locator("#story-reset")
        progress=page.locator("#story-progress")
        assert next_button.count()==1 and reset_button.count()==1,"story buttons missing"
        assert "Étape 0 / 10" in progress.inner_text(),"initial state invalid"
        for i in range(1,11):
            next_button.click()
            line=progress.inner_text()
            assert f"Étape {i} / 10" in line,f"wrong step {i}: {line}"
            count=page.locator("#story-events > section").count()
            assert count==i,f"expected {i} events, got {count}"
            events.append({"step":i,"status":"PASS"})
        assert next_button.is_disabled(),"last step must disable next"
        reset_button.click()
        assert "Étape 0 / 10" in progress.inner_text(),"reset does not return to start"
        assert page.locator("#story-events > section").count()==0,"reset left events"
        assert next_button.is_enabled(),"next button not re-enabled on reset"
        assert not writes,f"unexpected HTTP write requests: {writes}"
        browser.close()
    return {"status":"PASS","scope":"BROWSER_READ_ONLY","http":200,
            "steps":events,"reset":"PASS","no_http_writes":"PASS"}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--url",default="http://10.79.94.202:17777/policy-story")
    args=ap.parse_args()
    try:
        result=check(args.url)
    except ImportError:
        result={"status":"UNAVAILABLE","reason":"Playwright missing; no test performed"}
    except Exception as exc:
        result={"status":"FAIL","reason":f"{type(exc).__name__}: {exc}"}
    result["timestamp"]=datetime.now(timezone.utc).isoformat()
    result["limitation"]="Does not validate DGX, HITL, or real operational policy."
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result["status"]=="PASS" else 2
if __name__=="__main__":raise SystemExit(main())
