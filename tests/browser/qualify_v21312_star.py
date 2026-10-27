"""V2.13.12 regression: playback timing, presenter mode, responsive viewport.
Usage: python qualify_v21312_star.py --url file:///.../AIOPS-EXECUTIVE-THEATER-PUBLIC.html --output report.json
For http(s) supply the portal URL ending in /demo/star. Never mutates backend state.
"""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", default="v21312-browser.json")
    args = parser.parse_args()
    checks, errors = {}, []
    out = Path(args.output)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda err: errors.append(str(err)))
        response = page.goto(args.url, wait_until="load", timeout=20000)
        checks["loaded"] = bool(response and response.status == 200) if args.url.startswith("http") else page.locator("#counter").count() == 1
        checks["initial_12"] = page.locator("#counter").inner_text() == "1 / 12" and page.locator("#steps button").count() == 12
        page.locator("#presenter").click()
        checks["presenter_hides_notes"] = page.evaluate("document.body.classList.contains('presenter')") and not page.locator("aside").is_visible()
        page.locator("#presenter").click()
        checks["presenter_restores_notes"] = page.locator("aside").is_visible()
        page.locator("#pace").select_option("5000")
        page.locator("#toggle").click()
        checks["playing_state"] = page.locator("#toggle").get_attribute("aria-pressed") == "true" and "5 s" in page.locator("#autostatus").inner_text()
        expect(page.locator("#counter")).to_have_text("2 / 12", timeout=8500)
        checks["automatic_advance"] = page.locator("#counter").inner_text() == "2 / 12"
        page.locator("#toggle").click()
        checks["paused_state"] = page.locator("#toggle").get_attribute("aria-pressed") == "false"
        page.wait_for_timeout(5500)
        checks["paused_does_not_advance"] = page.locator("#counter").inner_text() == "2 / 12"
        page.locator("#reset").click()
        checks["reset"] = page.locator("#counter").inner_text() == "1 / 12"
        page.set_viewport_size({"width": 390, "height": 844})
        checks["mobile_content_visible"] = page.locator("#headline").is_visible() and page.locator("#toggle").is_visible()
        checks["mobile_no_horizontal_overflow"] = page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2")
        checks["provenance"] = "SIMULATED_TARGET" in page.locator("body").inner_text()
        checks["no_js_errors"] = not errors
        page.screenshot(path=str(out.with_suffix(".png")), full_page=True)
        browser.close()
    report = {"scope": "V21312_BROWSER_FUNCTIONAL", "checks": checks, "passed": all(checks.values()), "errors": errors,
              "limitations": "Synthetic UI behavior only; not a DGX, Core, historical access or LIVE remediation certification."}
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 1)

if __name__ == "__main__":
    main()
