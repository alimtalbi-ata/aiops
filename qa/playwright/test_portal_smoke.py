"""Independent, read-only portal smoke harness. No LIVE actions or credentials."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pytest
from playwright.sync_api import Page, expect, sync_playwright

BASE_URL = os.getenv("AIOPS_QA_BASE_URL", "http://127.0.0.1:17777").rstrip("/")
ARTIFACT_DIR = Path(os.getenv("AIOPS_QA_ARTIFACT_DIR", "artifacts/team-d"))
VIEWPORTS = [(1440, 1000), (768, 1024), (390, 844), (320, 800)]
DENY_ONLY_ENDPOINTS = [
    ("GET", "/api/portal/bootstrap"),
    ("GET", "/api/portal/components"),
    ("POST", "/api/copilot"),
    ("POST", "/api/demo"),
    ("GET", "/api/noc/runtime-state"),
    ("GET", "/api/noc/correlation"),
    ("GET", "/api/noc/grafana-health"),
]


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        instance = p.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(
        viewport={"width": 1440, "height": 1000},
        ignore_https_errors=False,
        record_har_path=None,
    )
    tab = context.new_page()
    # Never print console payloads or request headers; they may contain credentials.
    tab.on("console", lambda _msg: None)
    tab.on("request", lambda _request: None)
    yield tab
    context.close()


def _same_origin_links(page: Page) -> list[str]:
    origin = urlparse(BASE_URL).netloc
    hrefs = page.locator("a[href]").evaluate_all(
        "(els) => els.map((a) => a.href).filter(Boolean)"
    )
    result = []
    for href in hrefs:
        parsed = urlparse(href)
        if parsed.netloc == origin and parsed.scheme in ("http", "https"):
            path = parsed.path or "/"
            if path not in result:
                result.append(path)
    return result


def _safe_screenshot(page: Page, route: str, width: int) -> None:
    if os.getenv("AIOPS_QA_CAPTURE", "0") != "1":
        return
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    # Mask all user-editable fields, including password/token inputs.
    page.locator("input, textarea, [contenteditable='true']").evaluate_all(
        "(els) => els.forEach((el) => { el.value = ''; el.textContent = ''; el.setAttribute('data-qa-redacted', 'true'); })"
    )
    digest = hashlib.sha256(route.encode("utf-8")).hexdigest()[:10]
    page.screenshot(
        path=str(ARTIFACT_DIR / f"portal-{digest}-{width}.png"),
        full_page=False,
        animations="disabled",
    )


@pytest.mark.browser
def test_home_and_discoverable_routes_desktop_mobile_refresh_history(page: Page):
    response = page.goto(BASE_URL + "/", wait_until="domcontentloaded")
    assert response is not None and response.status < 500
    routes = _same_origin_links(page)
    # Include the canonical story routes when present in this portal generation.
    for candidate in ("/demo/acme-impact", "/demo/explore-story",
                     "/demo/acme-incident-cockpit", "/itsm"):
        if candidate not in routes:
            routes.append(candidate)

    assert routes, "No same-origin portal routes discovered from the home page"
    for route in routes:
        for width, height in VIEWPORTS:
            page.set_viewport_size({"width": width, "height": height})
            result = page.goto(urljoin(BASE_URL + "/", route.lstrip("/")),
                               wait_until="domcontentloaded")
            assert result is not None, f"No HTTP response for {route}"
            assert result.status < 500, f"{route} returned HTTP {result.status}"
            expect(page.locator("body")).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                f"Horizontal overflow at {width}px on {route}"
            )
            # A refresh must preserve the URL and remain renderable.
            current = page.url
            page.reload(wait_until="domcontentloaded")
            assert page.url == current
            expect(page.locator("body")).to_be_visible()
            _safe_screenshot(page, route, width)

    # Exercise browser history without assuming a particular client-side router.
    if len(routes) > 1:
        page.goto(urljoin(BASE_URL + "/", routes[0].lstrip("/")))
        page.goto(urljoin(BASE_URL + "/", routes[1].lstrip("/")))
        page.go_back(wait_until="domcontentloaded")
        assert urlparse(page.url).path == routes[0]
        page.go_forward(wait_until="domcontentloaded")
        assert urlparse(page.url).path == routes[1]


@pytest.mark.browser
def test_run_selection_is_local_and_does_not_trigger_mutation(page: Page):
    page.goto(BASE_URL + "/", wait_until="domcontentloaded")
    buttons = page.locator("button[data-run-select]")
    if buttons.count() == 0:
        pytest.skip("No rendered Run selector in this portal state")
    before = page.url
    requests = []
    page.on("request", lambda req: requests.append((req.method, urlparse(req.url).path)))
    buttons.first.click()
    assert page.url == before
    assert not any(path.startswith("/api/") and method not in ("GET", "HEAD")
                   for method, path in requests), "Run selection caused an API mutation"


@pytest.mark.api
@pytest.mark.parametrize(("method", "path"), DENY_ONLY_ENDPOINTS)
def test_unauthenticated_sensitive_endpoints_fail_closed(page: Page, method: str, path: str):
    # No bearer/token is supplied. Any 2xx response is a boundary failure.
    response = page.request.fetch(
        urljoin(BASE_URL + "/", path.lstrip("/")),
        method=method,
        data={} if method == "POST" else None,
        headers={"Accept": "application/json", "Cache-Control": "no-store"},
    )
    assert response.status in (401, 403, 404, 405, 503), (
        f"{method} {path} unexpectedly returned HTTP {response.status}"
    )
    assert not (200 <= response.status < 300)
