"""Real Chromium operator readback; no mocked successful receipt or action."""
import json
from pathlib import Path
import re
import sys
from playwright.sync_api import sync_playwright,expect

origin,root=sys.argv[1:]
assert re.fullmatch(r"http://127\.0\.0\.1:[0-9]{4,5}",origin)
assert int(origin.rsplit(":",1)[1]) not in (7770,7777,7790)
root=Path(root)
assert root==Path("/tmp/aiops-v3-rootless-ci")
report=json.loads((root/"temporal-e17.json").read_text())
proof=json.loads((root/"temporal-e17-gamma.json").read_text())
rid=report["workflow_id"]
comparison=report["verification"]["comparison_run_id"]
receipt=report["action_receipt"]["receipt_id"]
digest=report["action_receipt_sha256"]
assert proof["action_receipt_sha256"]==digest
assert all(re.fullmatch(r"RUN-[A-F0-9]{16}",x) for x in (rid,comparison))
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True)
    page=browser.new_page()
    errors=[]
    page.on("pageerror",lambda e: errors.append(str(e)))
    page.goto(origin,wait_until="domcontentloaded")
    def select(a,b):
        page.locator("#e17-original").fill(a)
        page.locator("#e17-comparison").fill(b)
    def verified():
        expect(page.locator("#e17-state")).to_have_text("RECOVERED — server-verified synthetic lab measurements / DENY",timeout=45000)
        expect(page.locator("#e17-measures")).to_be_visible()
        for field,key in (("baseline","baseline_ms"),("incident","incident_ms"),("after","recovery_ms")):
            expect(page.locator("#e17-"+field)).to_have_text(f"{report['verification']['measurements'][key]:.3f} ms")
        for value in (rid,comparison,receipt,digest):
            expect(page.locator("#e17-proof")).to_contain_text(value)
    def cleared():
        expect(page.locator("#e17-state")).to_contain_text("UNKNOWN / DENY")
        expect(page.locator("#e17-measures")).to_be_hidden()
        expect(page.locator("#e17-proof")).to_be_empty()
    select(rid,comparison)
    with page.expect_response(lambda r:"/api/v1/e17/recovery?" in r.url) as reply:
        page.locator("#e17-read").click()
    response=reply.value
    assert response.status==200
    assert response.json()["worker"]["action_receipt_sha256"]==digest
    assert "authorization" not in response.request.headers
    verified()
    # Selection change instantly clears the displayed proof; wrong run fails closed.
    select(comparison,rid)
    cleared()
    page.locator("#e17-read").click()
    expect(page.locator("#e17-state")).to_have_text("UNKNOWN / DENY — recovery not verified",timeout=45000)
    cleared()
    select(rid,comparison)
    # Delay the actual successful response without altering or fabricating it.
    def stale(route):
        real=route.fetch(timeout=40000)
        assert real.status==200 and real.json()["worker"]["action_receipt_sha256"]==digest
        page.locator("#e17-comparison").fill(rid)
        route.fulfill(response=real)
    page.route("**/api/v1/e17/recovery?*",stale,times=1)
    with page.expect_response(lambda r:"/api/v1/e17/recovery?" in r.url):
        page.locator("#e17-read").click()
    page.wait_for_timeout(250)
    cleared()
    select(rid,comparison)
    page.locator("#e17-read").click()
    verified()
    page.locator("#clear").click()
    cleared()
    assert not errors,errors
    browser.close()
print(json.dumps({"classification":"V3_GAMMA_E17_OPERATOR_BROWSER","result":"PASS",
                  "original_run_id":rid,"comparison_run_id":comparison,
                  "action_receipt_sha256":digest,"verification":"RECOVERED",
                  "stale_response_rejected":True,"production_authorized":False},sort_keys=True))
