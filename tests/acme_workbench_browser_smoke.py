"""Chromium loopback smoke: real DOM, no external origins or service reads.

Starts only a test-only ASGI app; no deployed host, secrets or mutations.
"""
import os
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
        [sys.executable, "-m", "uvicorn", "tests.acme_workbench_browser_app:app",
         "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
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
                    link.click()
                    assert page.url == base + "/acme-workbench"
                    assert page.get_by_text("NO_GO").count() >= 1
                    assert page.get_by_text("NON IMPLÉMENTÉ").count() >= 1
                    assert page.get_by_text("REMEDIATION_EFFECT").count() >= 1
                    assert page.get_by_text("LEARN", exact=True).count() >= 1
                    assert not blocked, f"external request attempted: {blocked}"
                    assert page.locator("input[type=password]").count() == 0
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
    print("PASS: isolated Chromium navigation at 375px and 1440px; no external requests")


if __name__ == "__main__":
    main()
