"""Playwright offline screenshot runner: local HTML fixtures only.

Requires an explicitly supplied local fixture per cue. Browser cannot navigate to
n8n/GLPI/Grafana; every network request is aborted, with no saved auth state.
These images are TEST FIXTURES, not runtime/business evidence.
"""
from __future__ import annotations
import asyncio
import hashlib
import json
from pathlib import Path

def validate_fixture_plan(plan: dict, fixtures: dict, root: Path) -> list[tuple[str, Path]]:
    if not isinstance(plan, dict) or plan.get("schema") != "star-browser-capture-tasks-v1":
        raise ValueError("invalid capture tasks")
    if plan.get("browser_executed") is not False or plan.get("runtime_proof_count") != 0 or plan.get("live_action_authorized") is not False:
        raise ValueError("unsafe capture claims")
    if not isinstance(fixtures, dict) or not isinstance(root, Path) or root.is_symlink():
        raise ValueError("invalid fixture root")
    base = root.resolve(strict=True)
    if not base.is_dir():
        raise ValueError("fixture root must be a directory")
    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or len(tasks) > 9 or set(fixtures) != {t.get("cue") for t in tasks if isinstance(t, dict)}:
        raise ValueError("one fixture required per planned cue")
    reviewed = []
    for task in tasks:
        if not isinstance(task, dict) or task.get("capture_performed") is not False or task.get("authenticated_runtime_proof") is not False:
            raise ValueError("forged task state")
        cue = task.get("cue")
        name = fixtures[cue]
        if not isinstance(name, str) or not name.endswith(".html") or "/" in name or "\\" in name or name.startswith("."):
            raise ValueError("unsafe fixture path")
        file = base / name
        if file.is_symlink() or not file.is_file() or file.resolve().parent != base or file.stat().st_size > 256000:
            raise ValueError("invalid fixture file")
        reviewed.append((cue, file))
    return reviewed

async def render_isolated_fixtures(plan: dict, fixtures: dict, root: Path, output: Path) -> dict:
    reviewed = validate_fixture_plan(plan, fixtures, root)
    if output.exists() or output.is_symlink():
        raise ValueError("output exists")
    # Optional dependency imported only after validation.
    from playwright.async_api import async_playwright
    output.mkdir(parents=True, exist_ok=False)
    captures = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(service_workers="block", accept_downloads=False)
            await context.route("**/*", lambda route: route.abort())
            for cue, path in reviewed:
                html = path.read_text(encoding="utf-8")
                page = await context.new_page()
                try:
                    await page.set_content(html, wait_until="domcontentloaded", timeout=10000)
                    filename = cue + ".png"
                    image = output / filename
                    await page.screenshot(path=str(image), timeout=10000)
                    captures.append({"cue":cue,"file":filename,"sha256":hashlib.sha256(image.read_bytes()).hexdigest(),
                                     "origin":"SYNTHETIC_LOCAL_FIXTURE","runtime_authenticated":False,"business_state_verified":False})
                finally:
                    await page.close()
        finally:
            await browser.close()
    manifest = {"schema":"star-offline-fixture-screenshots-v1","run_id":plan.get("run_id"),
                "captures":captures,"runtime_proof_count":0,"live_action_authorized":False}
    (output / "manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest
