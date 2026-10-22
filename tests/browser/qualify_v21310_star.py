"""Real Chromium smoke test for one existing AIOps portal (no server startup).
Run with Playwright installed in a browser QA environment.
"""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://10.79.94.202:17777")
    p.add_argument("--output", default="v21310-browser-report.json")
    args = p.parse_args()
    base = args.url.rstrip("/")
    events = []
    errors = []
    checks = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        try:
            r = page.goto(base + "/demo/", wait_until="domcontentloaded", timeout=15000)
            checks["catalog_http_200"] = bool(r and r.status == 200)
            checks["star_link"] = page.locator('a[href="/demo/star"]').count() > 0
            r = page.goto(base + "/demo/star", wait_until="load", timeout=20000)
            checks["star_http_200"] = bool(r and r.status == 200)
            checks["html_has_visible_content"] = bool(page.locator("body").inner_text().strip())
            checks["interactive_controls_detected"] = page.locator("button").count() >= 1
            page.screenshot(path=str(Path(args.output).with_suffix(".png")), full_page=True)
            r = page.request.get(base + "/demo/view/AIOPS-REAL-STACK-REPLAY.html")
            checks["historical_denied_403"] = r.status == 403
            checks["no_js_errors"] = len(errors) == 0
            events.append({"buttons": page.locator("button").all_text_contents()[:25]})
        finally:
            browser.close()
    result = {"scope": "REAL_BROWSER_SMOKE_ONLY", "url": base, "checks": checks, "passed": all(checks.values()), "js_errors": errors, "observations": events,
              "limits": "Does not certify per-control play/pause semantics, access controls beyond listed paths, DGX or LIVE execution"}
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["passed"] else 1)

if __name__ == "__main__":
    main()
