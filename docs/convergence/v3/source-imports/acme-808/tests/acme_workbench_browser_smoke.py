"""Chromium loopback smoke: real DOM, no external origins or service reads.

Starts only a test-only ASGI app; no deployed host, secrets or mutations.
"""
import os
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import closing

from playwright.sync_api import sync_playwright


def main():
    with closing(socket.socket()) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    env = dict(os.environ, AIOPS_INTERNAL_TOKEN="CI-ONLY-FAKE-TOKEN-NO-RUNTIME-AUTHORITY",
               AIOPS_DEMO_LAUNCH_ENABLED="false")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "acme_workbench_browser_app:app",
         "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
        env=dict(env, PYTHONPATH="tests:app:."), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        for _ in range(80):
            if proc.poll() is not None:
                raise AssertionError("isolated ASGI server exited")
            try:
                with urllib.request.urlopen(base + "/health", timeout=0.3) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError("isolated ASGI server did not start")
        capture_dir = Path(os.environ.get("ACME_BROWSER_CAPTURE_DIR", "/tmp/acme-workbench-ci-captures"))
        capture_dir.mkdir(parents=True, exist_ok=True)
        captures = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                for width in (375, 1440):
                    page = browser.new_page(viewport={"width": width, "height": 900})
                    blocked = []
                    def guard(route):
                        url = route.request.url
                        if url.startswith(base + "/"):
                            route.continue_()
                        else:
                            blocked.append(url)
                            route.abort()
                    page.route("**/*", guard)
                    response = page.goto(base + "/demo-studio", wait_until="domcontentloaded")
                    assert response.status == 200
                    link = page.get_by_role("link", name="Workbench ACME")
                    assert link.count() == 1
                    with page.expect_navigation(url=base + "/acme-workbench") as navigation:
                        link.click()
                    workbench_response = navigation.value
                    assert page.url == base + "/acme-workbench"
                    # Inspect the actual Chromium navigation response, not only
                    # in-process ASGI TestClient assertions.
                    assert workbench_response is not None
                    assert workbench_response.status == 200
                    headers = workbench_response.headers
                    assert headers.get("cache-control") == "no-store, max-age=0"
                    assert headers.get("pragma") == "no-cache"
                    assert headers.get("x-content-type-options") == "nosniff"
                    assert headers.get("x-frame-options") == "DENY"
                    assert headers.get("referrer-policy") == "no-referrer"
                    assert "geolocation=()" in headers.get("permissions-policy", "")
                    assert "set-cookie" not in headers
                    assert page.get_by_text("Parcours de qualification").count() >= 1
                    assert page.get_by_text("NO_GO").count() >= 1
                    assert page.get_by_text("NON IMPLÉMENTÉ").count() >= 1
                    assert page.get_by_text("REMEDIATION_EFFECT").count() >= 1
                    assert page.get_by_text("LEARN", exact=True).count() >= 1
                    assert not blocked, f"external request attempted: {blocked}"
                    assert page.locator("input[type=password]").count() == 0
                    capture_path = capture_dir / f"workbench-{width}.png"
                    page.screenshot(path=str(capture_path), full_page=True, animations="disabled")
                    raw = capture_path.read_bytes()
                    assert raw.startswith(bytes.fromhex("89504e470d0a1a0a"))
                    captures.append({
                        "viewport_width": width,
                        "file": capture_path.name,
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "size_bytes": len(raw),
                        "browser_status": "PASS_ISOLATED_BROWSER_ONLY",
                    })
                    page.close()
            finally:
                browser.close()
    finally:
        proc.terminate()
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate(timeout=5)
    manifest = {
        "schema": "aiops.acme-isolated-browser-png-manifest.v1",
        "authority": "CI_LOOPBACK_TEST_APP_NOT_DEPLOYED",
        "status": "PASS_ISOLATED_BROWSER_ONLY",
        "deployed_sha_attested": False,
        "runtime_e2e_verified": False,
        "viewer_acl_verified": False,
        "remediation_effect_verified": False,
        "learning_verified": False,
        "captures": captures,
    }
    (capture_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PASS: isolated Chromium navigation at 375px and 1440px; PNG captures hashed")


if __name__ == "__main__":
    main()
