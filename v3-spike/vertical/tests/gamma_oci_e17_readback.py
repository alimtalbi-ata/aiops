"""Read-only Chromium check of persisted E17 runs on an isolated GAMMA lab.

The caller supplies independently observed run IDs, receipt digest and outcome.
No target mutation or fabricated API response. The late-response subtest holds
an unchanged upstream response; it is browser fault injection, not recovery proof.
"""
import argparse
import asyncio
import json
import os
import re
from pathlib import Path
from urllib.parse import urlencode

from playwright.async_api import async_playwright, expect

ORIGIN = "http://127.0.0.1:18080"
RUN = r"RUN-[A-F0-9]{16}"
SHA = r"[a-f0-9]{64}"


def arguments():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("out", type=Path)
    p.add_argument("original")
    p.add_argument("comparison")
    p.add_argument("receipt_sha256")
    p.add_argument("status", choices=("RECOVERED", "NOT_RECOVERED"))
    a = p.parse_args()
    if a.original == a.comparison or not all(re.fullmatch(RUN, x) for x in (a.original, a.comparison)):
        p.error("two distinct E17 run IDs required")
    if not re.fullmatch(SHA, a.receipt_sha256):
        p.error("expected receipt SHA256 required")
    root = Path(os.environ.get("V3_ROOT", "/srv/aiops-v3")).resolve()
    a.out = a.out.resolve()
    if not a.out.is_relative_to(root) or a.out == root or a.out.exists():
        p.error("new output directory below V3_ROOT required")
    return a


async def main(a):
    a.out.mkdir(parents=True, mode=0o700)
    url = ORIGIN + "/api/v1/e17/recovery?" + urlencode({"original_run_id": a.original, "comparison_run_id": a.comparison})
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(service_workers="block")
        await ctx.tracing.start(screenshots=True, snapshots=True, sources=False)
        page = await ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        original = page.locator("#e17-original")
        comparison = page.locator("#e17-comparison")
        state = page.locator("#e17-state")
        measures = page.locator("#e17-measures")
        proof = page.locator("#e17-proof")
        read = page.locator("#e17-read")

        async def select_pair():
            await original.fill(a.original)
            await comparison.fill(a.comparison)

        async def unknown():
            await expect(state).to_contain_text("UNKNOWN / DENY")
            await expect(measures).to_be_hidden()
            await expect(proof).to_have_text("")

        async def verify_projection(d):
            w, v = d["worker"], d["verification"]
            r, m = w["action_receipt"], v["measurements"]
            assert d["classification"] == "SYNTHETIC_GAMMA_E17_VERIFIED_READBACK"
            assert all(x["production_authorized"] is False and x["operational_decision"] == "DENY" for x in (d, w, r, v, m))
            assert r["executed_on_host"] is False and r["status"] == "SIMULATED"
            assert w["run_id"] == r["binding"]["workflow_id"] == v["original_run_id"] == a.original
            assert v["comparison_run_id"] == a.comparison
            assert w["action_receipt_sha256"] == v["action_receipt_sha256"] == a.receipt_sha256
            assert r["receipt_id"] == v["action_receipt_id"] and v["status"] == a.status
            assert v["causality_established"] is False and m["causality_established"] is False
            await expect(state).to_have_text(a.status + " — server-verified synthetic lab measurements / DENY")
            await expect(measures).to_be_visible()
            for field, key in (("baseline", "baseline_ms"), ("incident", "incident_ms"), ("after", "recovery_ms")):
                value = m[key]
                assert value > 0
                await expect(page.locator("#e17-" + field)).to_have_text(f"{value:.3f} ms")
            for token in (a.original, a.comparison, r["receipt_id"], a.receipt_sha256):
                await expect(proof).to_contain_text(token)
            for scope in ("original_evidence", "comparison_evidence"):
                assert v[scope]
                for e in v[scope]:
                    await expect(proof).to_contain_text(e["evidence_id"] + " | " + e["payload_hash"])
            return v

        try:
            await page.goto(ORIGIN, wait_until="domcontentloaded")
            await select_pair()
            async with page.expect_response(lambda r: r.url == url, timeout=30000) as pending:
                await read.click()
            response = await pending.value
            assert response.ok, response.status
            d = await response.json()
            v = await verify_projection(d)
            await page.screenshot(path=str(a.out / "e17-readback.png"), full_page=True)

            # A real successful response is delayed unchanged, after upstream fetch.
            held, release = asyncio.Event(), asyncio.Event()
            async def delay(route):
                upstream = await route.fetch(timeout=30000, max_redirects=0)
                assert upstream.ok, upstream.status
                held.set()
                await release.wait()
                await route.fulfill(response=upstream)
            await page.route(url, delay)
            try:
                await read.click()
                await asyncio.wait_for(held.wait(), timeout=35)
                await comparison.fill(a.original)
                await unknown()
                async with page.expect_request_finished(lambda r: r.url == url, timeout=30000):
                    release.set()
                await page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
                await unknown()
            finally:
                release.set()
                await page.unroute(url, delay)

            # A duplicate pair must not initiate an E17 request or expose old proof.
            requests = []
            def seen(r):
                if r.url.startswith(ORIGIN + "/api/v1/e17/recovery?"):
                    requests.append(r.url)
            page.on("request", seen)
            await read.click()
            await unknown()
            assert not requests
            page.remove_listener("request", seen)
            await select_pair()
            async with page.expect_response(lambda r: r.url == url, timeout=30000) as pending:
                await read.click()
            response = await pending.value
            assert response.ok
            await verify_projection(await response.json())
            await page.locator("#clear").click()
            await unknown()
            assert not errors, errors
            report = {"classification": "PACKAGED_GAMMA_E17_READBACK", "result": "PASS", "original_run_id": a.original,
                      "comparison_run_id": a.comparison, "receipt_sha256": a.receipt_sha256, "status": a.status,
                      "measurements": v["measurements"], "late_response": "PASS", "duplicate_pair": "PASS", "reset": "PASS",
                      "production_authorized": False, "limitations": "Readback only; independent workflow history and target effects must be qualified by B/C/D."}
            (a.out / "e17-browser.json").write_text(json.dumps(report, sort_keys=True) + "\n")
            print(json.dumps(report, sort_keys=True))
        finally:
            await ctx.tracing.stop(path=str(a.out / "trace.zip"))
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main(arguments()))
