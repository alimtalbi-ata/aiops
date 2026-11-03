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
import sys
import tempfile
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
    page.screenshot(path=str(dest), full_page=True, animations="disabled")
    os.chmod(dest, 0o600)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    receipt["screenshots"].append({
        "name": dest.name, "bytes": dest.stat().st_size, "sha256": digest,
        "viewport": page.viewport_size,
    })


def run(args) -> dict:
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
        "blocked_requests_count": 0,
        "status": "FAIL",
    }
    # Imports are deferred so missing browser tooling fails with a precise error.
    from playwright.sync_api import sync_playwright, expect

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                service_workers="block", accept_downloads=False,
            )
            page = context.new_page()
            errors = []
            blocked = []

            def fence(route):
                request = route.request
                target = urlsplit(request.url)
                root = urlsplit(base)
                if (target.scheme == root.scheme and target.hostname == root.hostname
                        and target.port == root.port and request.method == "GET"):
                    route.continue_()
                else:
                    blocked.append((request.method, target.scheme))
                    route.abort()

            context.route("**/*", fence)
            page.on("pageerror", lambda _: errors.append("PAGE_ERROR"))

            def visit(label, path, selector, expected):
                response = page.goto(base + path, wait_until="domcontentloaded", timeout=15000)
                if response is None or response.status != 200:
                    raise AssertionError(label + " HTTP response failed")
                expect(page.locator(selector)).to_contain_text(expected, timeout=10000)
                if label == "01-overview":
                    expect(page.locator("#fixture-status")).to_contain_text(
                        "Référence locale chargée", timeout=10000)
                if label == "04-connections":
                    expect(page.locator("#session-status")).to_contain_text(
                        "Aucune session d\u0027entreprise valide", timeout=10000)
                receipt["checks"].append({"name": label, "status": "PASS"})
                capture(page, folder, label, receipt)

            visit("01-overview", "/", *MARKERS["overview"])
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
                response = mp.goto(base + "/", wait_until="domcontentloaded", timeout=15000)
                if response is None or response.status != 200:
                    raise AssertionError("mobile home unavailable")
                expect(mp.locator("#overview-heading")).to_be_visible()
                if mp.evaluate("document.documentElement.scrollWidth > window.innerWidth + 2"):
                    raise AssertionError("mobile horizontal overflow")
                capture(mp, folder, "09-mobile-overview", receipt)
                receipt["checks"].append({"name": "mobile-390px", "status": "PASS"})
            finally:
                mobile.close()

            receipt["page_errors_count"] = len(errors)
            receipt["blocked_requests_count"] = len(blocked)
            if errors:
                raise AssertionError("JavaScript pageerror observed")
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
            "status": "FAIL", "failure_type": type(exc).__name__,
            "real_screen_capture": "NOT_VERIFIED", "live_effects": 0,
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
