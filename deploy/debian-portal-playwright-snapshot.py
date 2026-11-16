#!/usr/bin/env python3
"""P0 #396 read-only Chromium screenshot qualification ON the target Debian host.

Run locally on SRV-DEB-05; this is NOT a CI synthetic screenshot:
  python3 -m pip install --user playwright==1.55.0
  python3 -m playwright install chromium
  python3 deploy/debian-portal-playwright-snapshot.py \
    --base-url http://127.0.0.1:7777 \
    --assert-host SRV-DEB-05 \
    --output-dir /home/aiops/.local/state/aiops-debian-agent/portal-playwright

Uses a fresh anonymous browser context. All requests must be GET and same-origin.
Never enters credentials, approves an action, starts screen recording or writes
to Core/GLPI/n8n/Worker. Screenshots remain LOCAL, mode 0600, without uploads.
Real screen recording, human SSO/ACL and HTTPS remain separately NOT_VERIFIED.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

MARKERS = {
    "overview": ("#overview-heading", "Comprendre l'incident"),
    "journey": ("#journey-heading", "Du signal à la décision"),
    "runs": ("#runs-heading", "Une seule chronologie"),
    "connections": ("#connections-heading", "Vos accès, sans jeton"),
}
PAGES = (
    ("demo-center", "/demo-center", "SIMULATION_ONLY"),
    ("recorder-station", "/demo-center/recorder", "LOCAL_ONLY / NO LIVE EFFECT"),
    ("demo-studio", "/demo-studio", "SYNTHETIC_REFERENCE_ONLY"),
    ("noc", "/noc", "SYNTHETIC_REFERENCE_ONLY"),
)
SENSITIVE_NAMES = ("portal-read-token", "noc-token", "demo-token", "portal-navigation-token")
# CLI-only bounded diagnostic state. No messages, URLs, headers or tokens.
BROWSER_PROGRESS = {"stage": "NOT_STARTED", "page_errors_count": 0,
                    "console_errors_count": 0, "failed_requests_count": 0,
                    "blocked_requests_count": 0, "console_error_class": "none",
                    "failed_request_class": "none", "console_error_stage": "none",
                    "failed_request_stage": "none", "failed_request_diagnostics": []}


def classify_console_error(msg):
    """Return a fixed enum; never persist browser text, headers or URLs."""
    value = str(getattr(msg, "text", ""))
    if "Failed to load resource" in value and "401" in value:
        return "http_401_resource"
    if "Failed to load resource" in value and "404" in value:
        return "http_404_resource"
    if "Refused to" in value or "Content Security Policy" in value:
        return "csp_rejected"
    return "other_console_error"


def classify_failed_request(request):
    value = str(getattr(request, "failure", "") or "")
    if "ERR_ABORTED" in value:
        return "aborted"
    if "ERR_CONNECTION" in value or "ERR_NETWORK" in value:
        return "connection"
    return "other_request_failure"


def request_diagnostic(request, stage):
    """Bounded request category only: never persist URLs, queries or credentials."""
    path = urlsplit(str(getattr(request, "url", ""))).path
    if path == "/api/portal/session":
        endpoint = "anonymous_session"
    elif path in ("/", "/workspace", "/runs"):
        endpoint = "portal_document"
    elif path.startswith("/api/"):
        endpoint = "other_api"
    elif path.startswith("/static/"):
        endpoint = "static_asset"
    else:
        endpoint = "other_resource"
    kind = str(getattr(request, "resource_type", "unknown"))
    if kind not in ("document", "script", "stylesheet", "image", "font",
                    "fetch", "xhr", "other"):
        kind = "other"
    return {"stage": stage, "endpoint_class": endpoint,
            "resource_type": kind, "failure_class": classify_failed_request(request)}


def note_failure(kind):
    if kind in BROWSER_PROGRESS and kind.endswith("_count"):
        BROWSER_PROGRESS[kind] += 1



def verify_base_url(raw: str) -> str:
    try:
        value = urlsplit(raw)
        if (value.scheme not in ("http", "https") or not value.hostname
                or value.username or value.password or value.query or value.fragment
                or value.path not in ("", "/") or not value.port
                or (value.scheme == "http" and value.hostname not in
                    ("127.0.0.1", "localhost", "::1"))):
            raise ValueError
        return raw.rstrip("/")
    except (TypeError, ValueError) as exc:
        raise ValueError("Use an explicit local HTTP origin or a reviewed HTTPS origin") from exc


def secure_dir(path: Path) -> None:
    if path.exists() and path.is_symlink():
        raise OSError("output directory must not be a symlink")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)


def save_receipt(path: Path, receipt: dict) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".playwright-", dir=path)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(receipt, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
        os.replace(tmp, path / "portal-playwright-receipt.json")
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def capture(page, folder: Path, name: str, receipt: dict) -> None:
    if re.fullmatch(r"[a-z0-9-]{3,50}", name) is None:
        raise ValueError("invalid screenshot name")
    dest = folder / (name + ".png")
    # Playwright's path= write may briefly create a world-readable file under
    # the host umask and may follow an existing screenshot symlink. Keep bytes
    # in memory, write to a private temporary file, then atomically replace.
    data = page.screenshot(full_page=True, animations="disabled")
    if not isinstance(data, bytes) or not data:
        raise ValueError("empty screenshot")
    fd, tmp = tempfile.mkstemp(prefix=".shot-", suffix=".png", dir=folder)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(tmp, dest)  # replaces a symlink, never follows its target
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    receipt["screenshots"].append({
        "name": dest.name, "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "viewport": page.viewport_size,
    })



def observed_provenance(runner=subprocess.run) -> dict:
    """Read exact local checkout and Docker image IDs, never environment/labels."""
    def probe(argv):
        try:
            result = runner(argv, capture_output=True, text=True, timeout=8, check=False)
            return result.stdout.strip() if result.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None
    stable = probe(["git", "-C", str(Path(__file__).resolve().parents[1]),
                    "rev-parse", "HEAD"])
    image = probe(["docker", "inspect", "--type", "container", "--format",
                   "{{.Image}}", "aiops2-rebuild-portal"])
    return {
        "stable_checkout_sha": stable if isinstance(stable, str)
        and re.fullmatch(r"[0-9a-f]{40}", stable) else None,
        "portal_image_id": image if isinstance(image, str)
        and re.fullmatch(r"sha256:[0-9a-f]{64}", image) else None,
    }


def await_synthetic_workspace_ready(page, expect) -> None:
    """Wait for the one known asynchronous read, not global network quiescence.

    The anonymous operator workspace loads a strictly local synthetic fixture
    and can independently probe a fail-closed session endpoint. A permanent
    background request must never turn an otherwise rendered page into a
    networkidle timeout. An unavailable fixture must still fail this gate.
    """
    expect(page.locator("#fixture-status")).to_have_attribute(
        "data-state", "ready", timeout=10000)


def await_session_request_finished(page, pending, timeout_ms=5000):
    """Do not navigate away while the known fail-closed session GET is active."""
    deadline = time.monotonic() + timeout_ms / 1000
    while pending and time.monotonic() < deadline:
        page.wait_for_timeout(50)
    if pending:
        raise AssertionError("session request did not finish before navigation")


def run(args) -> dict:
    BROWSER_PROGRESS.update(stage="VERIFY_HOST", page_errors_count=0,
                            console_errors_count=0, failed_requests_count=0,
                            blocked_requests_count=0, console_error_class="none",
                            failed_request_class="none", console_error_stage="none",
                            failed_request_stage="none", failed_request_diagnostics=[])
    base = verify_base_url(args.base_url)
    hostname = platform.node()
    if args.assert_host and hostname.casefold().split(".")[0] != args.assert_host.casefold():
        raise ValueError("hostname does not match the requested Debian host")
    folder = Path(args.output_dir).expanduser().absolute()
    secure_dir(folder)
    receipt = {
        "schema": "aiops.portal-host-playwright-snapshots.v1",
        "collected_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "host": hostname,
        "host_asserted": bool(args.assert_host),
        "origin": base,
        "mode": "ANONYMOUS_SYNTHETIC_UI_ONLY",
        "real_screen_capture": "NOT_VERIFIED",
        "human_glpi_acl": "NOT_VERIFIED",
        "n8n_login": "NOT_VERIFIED",
        "oidc_https": "NOT_VERIFIED" if base.startswith("http:") else "NOT_TESTED",
        "live_effects": 0,
        "checks": [],
        "screenshots": [],
        "page_errors_count": 0,
        "console_errors_count": 0,
        "failed_requests_count": 0,
        "blocked_requests_count": 0,
        "status": "FAIL",
    }
    receipt.update(observed_provenance())
    BROWSER_PROGRESS["stage"] = "IMPORT_PLAYWRIGHT"
    # Imports are deferred so missing browser tooling fails with a precise error.
    from playwright.sync_api import sync_playwright, expect

    with sync_playwright() as playwright:
        BROWSER_PROGRESS["stage"] = "LAUNCH_CHROMIUM"
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                service_workers="block", accept_downloads=False,
            )
            page = context.new_page()
            errors = []
            console_errors = []
            failed_requests = []
            blocked = []
            pending_session = set()
            denied_session_responses = []

            def record_request(request):
                if urlsplit(request.url).path == "/api/portal/session":
                    pending_session.add(request)

            def record_request_finished(request):
                pending_session.discard(request)

            def record_response(response):
                if (urlsplit(response.url).path == "/api/portal/session"
                        and response.status == 401):
                    denied_session_responses.append("EXPECTED_SESSION_401")

            def fence(route):
                request = route.request
                target = urlsplit(request.url)
                root = urlsplit(base)
                if (target.scheme == root.scheme and target.hostname == root.hostname
                        and target.port == root.port and request.method == "GET"):
                    route.continue_()
                else:
                    blocked.append((request.method, target.scheme))
                    note_failure("blocked_requests_count")
                    route.abort()

            context.route("**/*", fence)
            def record_console(msg):
                if msg.type != "error":
                    return
                console_errors.append("CONSOLE_ERROR")
                note_failure("console_errors_count")
                BROWSER_PROGRESS["console_error_class"] = classify_console_error(msg)
                BROWSER_PROGRESS["console_error_stage"] = BROWSER_PROGRESS["stage"]

            def record_request_failure(request):
                pending_session.discard(request)
                failed_requests.append("REQUEST_FAILED")
                note_failure("failed_requests_count")
                BROWSER_PROGRESS["failed_request_class"] = classify_failed_request(request)
                BROWSER_PROGRESS["failed_request_stage"] = BROWSER_PROGRESS["stage"]
                if len(BROWSER_PROGRESS["failed_request_diagnostics"]) < 8:
                    BROWSER_PROGRESS["failed_request_diagnostics"].append(
                        request_diagnostic(request, BROWSER_PROGRESS["stage"]))

            page.on("pageerror", lambda _: (errors.append("PAGE_ERROR"),
                                             note_failure("page_errors_count")))
            page.on("console", record_console)
            page.on("requestfailed", record_request_failure)
            page.on("request", record_request)
            page.on("requestfinished", record_request_finished)
            page.on("response", record_response)

            def visit(label, path, selector, expected):
                BROWSER_PROGRESS["stage"] = label
                response = page.goto(base + path, wait_until="domcontentloaded", timeout=15000)
                # Playwright returns None for a same-document fragment navigation.
                if response is None and not path.startswith("/#"):
                    raise AssertionError(label + " HTTP response missing")
                if response is not None and response.status != 200:
                    raise AssertionError(label + " HTTP response failed")
                if page.url != base + path:
                    raise AssertionError(label + " unexpected origin or route")
                expect(page.locator(selector)).to_contain_text(expected, timeout=10000)
                # Wait for document resources, then the exact async fixture
                # contract on workspace routes. networkidle is not reliable
                # when an unrelated session/poll request remains active.
                page.wait_for_load_state("load", timeout=10000)
                if path in ("/", "/runs", "/#journey", "/#connections"):
                    await_synthetic_workspace_ready(page, expect)
                if label == "01-overview":
                    expect(page.locator("#fixture-status")).to_contain_text(
                        "Référence locale chargée", timeout=10000)
                if label == "04-connections":
                    expect(page.locator("#session-status")).to_contain_text(
                        "Aucune session d\u0027entreprise valide", timeout=10000)
                    await_session_request_finished(page, pending_session)
                receipt["checks"].append({"name": label, "status": "PASS"})
                capture(page, folder, label, receipt)

            visit("01-overview", "/", *MARKERS["overview"])
            BROWSER_PROGRESS["stage"] = "fixture-contract"
            expect(page.locator("#fixture-status")).to_contain_text(
                "Référence locale chargée", timeout=10000)
            if page.locator('input[type="password"]').count() != 0:
                raise AssertionError("manual bearer field present in modern home")
            for name in SENSITIVE_NAMES:
                if page.locator("#" + name).count() != 0:
                    raise AssertionError("legacy bearer field present")
            if page.locator("#impact-path li").count() < 2:
                raise AssertionError("synthetic graph missing")
            if page.locator("#ci-count").inner_text() != "6":
                raise AssertionError("synthetic CI count is not the local fixture")
            receipt["checks"].append({"name": "synthetic-fixture-no-token", "status": "PASS"})

            visit("02-journey", "/#journey", *MARKERS["journey"])
            if page.locator("#scenario-select option").count() != 8:
                raise AssertionError("eight teaching scenarios not mounted")
            BROWSER_PROGRESS["stage"] = "scenario-catalog"
            page.locator("#scenario-select").select_option("storm")
            expect(page.locator("#scenario-description")).to_contain_text(
                "Aucune alarme n'est supprimée")
            receipt["checks"].append({"name": "eight-catalog-only", "status": "PASS"})

            visit("03-runs", "/runs", *MARKERS["runs"])
            expect(page.locator("#runs")).to_contain_text(
                "Liste d'incidents réels non disponible")
            if page.locator('input[type="password"]').count() != 0:
                raise AssertionError("manual bearer present on runs")

            visit("04-connections", "/#connections", *MARKERS["connections"])
            if base.startswith("http:"):
                if page.locator("#sso-link").get_attribute("href") is not None:
                    raise AssertionError("insecure HTTP SSO link should be disabled")
                receipt["checks"].append({"name": "http-oidc-fail-closed", "status": "PASS"})

            for label, path, marker in PAGES:
                visit(label, path, "body", marker)

            mobile = browser.new_context(
                viewport={"width": 390, "height": 844},
                service_workers="block", accept_downloads=False,
            )
            try:
                mobile.route("**/*", fence)
                mp = mobile.new_page()
                BROWSER_PROGRESS["stage"] = "mobile-390px"
                mp.on("pageerror", lambda _: (errors.append("PAGE_ERROR"),
                                             note_failure("page_errors_count")))
                mp.on("console", record_console)
                mp.on("requestfailed", record_request_failure)
                response = mp.goto(base + "/", wait_until="domcontentloaded", timeout=15000)
                if response is None or response.status != 200:
                    raise AssertionError("mobile home unavailable")
                expect(mp.locator("#overview-heading")).to_be_visible()
                mp.wait_for_load_state("load", timeout=10000)
                await_synthetic_workspace_ready(mp, expect)
                if mp.evaluate("document.documentElement.scrollWidth > window.innerWidth + 2"):
                    raise AssertionError("mobile horizontal overflow")
                capture(mp, folder, "09-mobile-overview", receipt)
                receipt["checks"].append({"name": "mobile-390px", "status": "PASS"})
            finally:
                mobile.close()

            BROWSER_PROGRESS["stage"] = "final-browser-diagnostics"
            receipt["page_errors_count"] = len(errors)
            receipt["console_errors_count"] = len(console_errors)
            receipt["failed_requests_count"] = len(failed_requests)
            receipt["blocked_requests_count"] = len(blocked)
            receipt["failed_request_diagnostics"] = list(BROWSER_PROGRESS["failed_request_diagnostics"])
            # A 401 from the exact anonymous session endpoint is a required
            # fail-closed response, not a JavaScript exception or granted ACL.
            # Never waive an unrelated console error or any failed request.
            expected_401 = int(
                len(console_errors) == 1
                and BROWSER_PROGRESS["console_error_class"] == "http_401_resource"
                and len(denied_session_responses) == 1
            )
            receipt["expected_session_401_console_count"] = expected_401
            receipt["unexpected_console_errors_count"] = len(console_errors) - expected_401
            if errors or receipt["unexpected_console_errors_count"] or failed_requests:
                raise AssertionError("browser JavaScript/console/network failure observed")
            if blocked:
                raise AssertionError("non-GET or off-origin request attempted")
            receipt["status"] = "PASS_ANONYMOUS_SYNTHETIC_BROWSER_ONLY"
            return receipt
        finally:
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:7777")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--assert-host", default="")
    args = parser.parse_args()
    folder = Path(args.output_dir).expanduser()
    try:
        result = run(args)
    except Exception as exc:
        # No secrets/URLs/exception message are persisted into the receipt.
        result = {
            "schema": "aiops.portal-host-playwright-snapshots.v1",
            "collected_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "host": platform.node(), "mode": "ANONYMOUS_SYNTHETIC_UI_ONLY",
            "host_asserted": bool(args.assert_host and
                platform.node().casefold().split(".")[0] == args.assert_host.casefold()),
            "origin": "http://127.0.0.1:7777" if args.base_url.rstrip("/") ==
                "http://127.0.0.1:7777" else "UNVERIFIED",
            "status": "FAIL", "failure_type": type(exc).__name__,
            "failure_stage": BROWSER_PROGRESS["stage"],
            **{k: BROWSER_PROGRESS[k] for k in (
                "page_errors_count", "console_errors_count",
                "failed_requests_count", "blocked_requests_count",
                "console_error_class", "failed_request_class",
                "console_error_stage", "failed_request_stage",
                "failed_request_diagnostics")},
            "real_screen_capture": "NOT_VERIFIED", "live_effects": 0,
            **observed_provenance(),
        }
    try:
        secure_dir(folder)
        save_receipt(folder, result)
    except OSError:
        print("PLAYWRIGHT_RECEIPT_WRITE_FAILED")
        return 78
    print("PORTAL_HOST_PLAYWRIGHT=" + result["status"])
    return 0 if result["status"] == "PASS_ANONYMOUS_SYNTHETIC_BROWSER_ONLY" else 78


if __name__ == "__main__":
    sys.exit(main())
