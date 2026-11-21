#!/usr/bin/env python3
"""Offline ACME Chromium navigation qualification. No Core calls."""
import argparse,json
from pathlib import Path
def verify(root):
    from playwright.sync_api import sync_playwright
    expected=("index.html","ACME-MISSION-CONTROL.html","ACME-HISTORICAL-AUDIT.html")
    for name in expected:
        if not (root/name).is_file():raise ValueError("missing page: "+name)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page()
        errors=[]
        page.on("pageerror",lambda x:errors.append(str(x)))
        page.goto((root/"index.html").as_uri())
        assert "PROVENANCES DIFFÉRENTES" in page.locator("body").inner_text()
        page.get_by_text("Explorer la simulation").click()
        assert page.locator("#scenario option").count()==6
        page.goto((root/"index.html").as_uri())
        page.get_by_text("Examiner les métadonnées").click()
        assert "RUN-A4449145A6E377FF" in page.locator("body").inner_text()
        assert page.locator("table").count()==2
        assert not errors,errors
        browser.close()
    return {"version":"2.12.7","pages":3,"navigation_checks":2,"status":"PASS",
      "dgx_independently_attested":False,"live_execution_qualified":False}
if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--kit",type=Path,required=True)
    args=a.parse_args()
    print(json.dumps(verify(args.kit),ensure_ascii=False))
