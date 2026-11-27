"""Real packaged GAMMA browser gate; no intercepted or fabricated responses."""
import json
import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ORIGIN = "http://127.0.0.1:18080"

def main(out):
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context()
        context.tracing.start(screenshots=True, snapshots=True, sources=False)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        def click_api(button, path):
            with page.expect_response(lambda r: r.url.startswith(ORIGIN + path), timeout=30000) as pending:
                page.locator(button).click()
            response = pending.value
            assert response.ok, (path, response.status)
            return response.json()
        try:
            page.goto(ORIGIN, wait_until="domcontentloaded")
            expect(page.locator("#dynamic-hitl-approve")).to_be_disabled()
            publication = click_api("#create-dynamic", "/api/v1/ingest/create")
            run = publication["core"]["run"]["run_id"]
            assert re.fullmatch(r"RUN-[A-F0-9]{16}", run)
            expect(page.locator("#dynamic-result")).to_contain_text(run)
            for evidence in publication["stored_evidence"]:
                expect(page.locator("#dynamic-result")).to_contain_text(evidence["payload_hash"])
            decisions = []
            for approved, expected in [(True, "SIMULATE_ONLY"), (False, "DENY")]:
                pending = click_api("#dynamic-hitl-request", "/api/v1/hitl/dynamic/request")
                result = click_api("#dynamic-hitl-approve" if approved else "#dynamic-hitl-deny", "/api/v1/hitl/dynamic/decide")
                assert result["run_id"] == run and result["decision"] == expected
                assert result["production_authorized"] is False and result["executed_on_host"] is False
                expect(page.locator("#dynamic-hitl-result")).to_contain_text(expected + " — " + run)
                replay = page.request.post(ORIGIN + "/api/v1/hitl/dynamic/decide", headers={"Origin": ORIGIN}, data={"run_id":run,"request_id":pending["request_id"],"approved":approved})
                assert replay.ok and replay.json()["decision"] == "DENY"
                decisions.append(expected)
            page.screenshot(path=str(out / "gamma-hitl.png"), full_page=True)
            page.locator("#clear").click()
            expect(page.locator("#dynamic-result")).to_have_text("UNKNOWN / DENY")
            expect(page.locator("#dynamic-hitl-approve")).to_be_disabled()
            page.locator("#e17-original").fill(run)
            page.locator("#e17-comparison").fill(run)
            page.locator("#e17-read").click()
            expect(page.locator("#e17-state")).to_contain_text("UNKNOWN / DENY")
            expect(page.locator("#e17-measures")).to_be_hidden()
            assert not errors, errors
            report = {"classification":"PACKAGED_GAMMA_CHROMIUM", "result":"PASS","run_id":run,"decisions":decisions,"e17":"NOT_RUN","production_authorized":False}
            (out / "browser.json").write_text(json.dumps(report, sort_keys=True))
            print(json.dumps(report, sort_keys=True))
        finally:
            context.tracing.stop(path=str(out / "trace.zip"))
            browser.close()

if __name__ == "__main__":
    main(Path(sys.argv[1]))
