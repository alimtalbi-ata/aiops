#!/usr/bin/env python3
"""Operator-opt-in, read-only Playwright capture for five real application views.

Ported request-fence design from PR #36 star_browser_request_fence.py.
Dry-run by default. No CI browsing, no mocked LIVE evidence, no action execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from datetime import datetime, timezone
from urllib.parse import urlsplit

from demo.evidence_publish import publish_capture_set

SERVICES = ("portal", "thruk", "grafana", "n8n", "glpi")
IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
SELECTOR = re.compile(r"^(?:[#.][A-Za-z][A-Za-z0-9_-]*)(?: [#.][A-Za-z][A-Za-z0-9_-]*)*$")
PNG = bytes.fromhex("89504e470d0a1a0a")


def origin(url):
    if not isinstance(url, str) or len(url) > 2048 or any(c.isspace() for c in url) or "\\" in url:
        raise ValueError("unsafe URL")
    try:
        u = urlsplit(url)
        port = u.port
    except ValueError as exc:
        raise ValueError("invalid URL port") from exc
    if (u.scheme not in ("http", "https") or not u.hostname or u.username is not None
            or u.password is not None or u.fragment or u.query or port == 0
            or u.netloc != u.netloc.lower() or u.hostname.endswith(".")):
        raise ValueError("noncanonical or credential-bearing URL")
    return f"{u.scheme}://{u.netloc}"


def validate_plan(plan):
    """Pure offline validation; no network, filesystem reads or browser startup."""
    if not isinstance(plan, dict) or plan.get("schema_version") != 1:
        raise ValueError("invalid capture plan")
    for field in ("run_id", "incident_id", "ticket_id", "session_label"):
        value = plan.get(field)
        if not isinstance(value, str) or not IDENT.fullmatch(value):
            raise ValueError("missing or invalid " + field)
    entries = plan.get("captures")
    if not isinstance(entries, list) or len(entries) != len(SERVICES):
        raise ValueError("exactly five captures required")
    seen = set()
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("invalid capture")
        service = item.get("service")
        if service not in SERVICES or service in seen:
            raise ValueError("duplicate or unknown service")
        seen.add(service)
        url = item.get("url")
        allowed = item.get("allowed_origin")
        if origin(url) != allowed or origin(allowed) != allowed:
            raise ValueError("capture origin not explicitly approved")
        if ".." in urlsplit(url).path.split("/"):
            raise ValueError("path traversal")
        urls = item.get("approved_get_urls", [])
        if not isinstance(urls, list) or len(urls) > 64 or len(set(urls)) != len(urls):
            raise ValueError("invalid GET allowlist")
        for resource in urls:
            if origin(resource) != allowed or resource == url:
                raise ValueError("GET resource outside approved origin")
        proof = item.get("proof_text")
        if proof not in (plan["run_id"], plan["incident_id"], plan["ticket_id"]):
            raise ValueError("proof must bind a declared incident/run/ticket ID")
        masks = item.get("redact_selectors")
        if not isinstance(masks, list) or not masks or len(masks) > 20:
            raise ValueError("explicit redaction selectors required")
        selectors = [item.get("proof_selector"), *masks]
        if any(not isinstance(s, str) or len(s) > 150 or not SELECTOR.fullmatch(s) for s in selectors):
            raise ValueError("unsafe CSS selector")
        if len(set(selectors)) != len(selectors):
            raise ValueError("proof selector cannot overlap redaction selectors")
    if seen != set(SERVICES):
        raise ValueError("missing application")
    return entries


def permits(item, url, method, navigation, main_frame):
    """Exact GET allowlist ported from PR #36; GET itself is not side-effect-free."""
    try:
        if method != "GET" or origin(url) != item["allowed_origin"]:
            return False
        if navigation:
            return main_frame and url == item["url"]
        return url in item.get("approved_get_urls", [])
    except (TypeError, ValueError, KeyError):
        return False


def capture(plan, output_dir, storage_state_dir, approved=False):
    entries = validate_plan(plan)
    if not approved:
        return {"status": "DRY_RUN", "captures_performed": 0, "runtime_authenticated": False}
    if os.environ.get("CI", "").lower() == "true" or os.environ.get("AIOPS_STAR_NO_RUNTIME") == "1":
        raise ValueError("runtime capture forbidden in CI/offline mode")
    if os.environ.get("AIOPS_CAPTURE_OPERATOR_APPROVED") != "YES":
        raise ValueError("explicit operator authorization required")
    output_dir = Path(output_dir)
    storage_state_dir = Path(storage_state_dir)
    if output_dir.is_symlink() or not output_dir.is_dir():
        raise ValueError("existing private output directory required")
    if storage_state_dir.is_symlink() or not storage_state_dir.is_dir():
        raise ValueError("private session state directory required")
    for directory in (output_dir, storage_state_dir):
        if stat.S_IMODE(directory.stat().st_mode) & 0o077:
            raise ValueError("private directory permissions required (chmod 700)")
    if any((output_dir / (s + ".png")).exists() or (output_dir / (s + ".png")).is_symlink() for s in SERVICES):
        raise ValueError("refusing to overwrite captures")
    if (output_dir / "manifest.json").exists() or (output_dir / "manifest.json").is_symlink():
        raise ValueError("refusing to overwrite manifest")
    for service in SERVICES:
        state = storage_state_dir / (service + ".json")
        if not state.is_file() or state.is_symlink():
            raise ValueError("missing or symlinked private browser session state")
        if stat.S_IMODE(state.stat().st_mode) & 0o077:
            raise ValueError("session state must be owner-only (chmod 600)")
    # Playwright is optional and imported only after authorization and validation.
    from playwright.sync_api import sync_playwright
    captures = []
    with tempfile.TemporaryDirectory(prefix=".capture-", dir=output_dir) as tmp:
        staging = Path(tmp)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                for item in entries:
                    service = item["service"]
                    context = browser.new_context(
                        storage_state=str(storage_state_dir / (service + ".json")),
                        service_workers="block", accept_downloads=False,
                        viewport={"width": 1440, "height": 900})
                    try:
                        page = context.new_page()
                        blocked = []
                        def gate(route):
                            request = route.request
                            try:
                                main = request.frame == page.main_frame
                            except Exception:
                                main = False
                            if permits(item, request.url, request.method,
                                       request.is_navigation_request(), main):
                                route.continue_()
                            else:
                                blocked.append(request.method + " " + request.url.split("?")[0])
                                route.abort()
                        page.route("**/*", gate)
                        response = page.goto(item["url"], wait_until="domcontentloaded", timeout=20000)
                        if response is None or response.status >= 400 or page.url != item["url"] or blocked:
                            raise ValueError("navigation failed or request denied for " + service)
                        proof = page.locator(item["proof_selector"])
                        if proof.count() != 1 or item["proof_text"] not in proof.inner_text(timeout=5000):
                            raise ValueError("correlation ID not visible for " + service)
                        masks = [page.locator(s) for s in item["redact_selectors"]]
                        if any(m.count() == 0 for m in masks):
                            raise ValueError("redaction target missing for " + service)
                        image = page.screenshot(type="png", full_page=False, mask=masks,
                                                animations="disabled", timeout=15000)
                        if blocked or not image.startswith(PNG) or len(image) > 20 * 1024 * 1024:
                            raise ValueError("blocked request or invalid screenshot for " + service)
                        image_path = staging / (service + ".png")
                        image_path.write_bytes(image)
                        image_path.chmod(0o600)
                        captures.append({
                            "service": service, "file": service + ".png",
                            "sha256": hashlib.sha256(image).hexdigest(),
                            "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                            "source_url": item["url"],
                            "capture_method": "PLAYWRIGHT_OPERATOR_SESSION_UNREVIEWED",
                            "session_label": plan["session_label"],
                            "run_id": plan["run_id"], "incident_id": plan["incident_id"],
                            "ticket_id": plan["ticket_id"],
                            "runtime_authenticated": False, "production_qualified": False,
                        })
                    finally:
                        context.close()
            finally:
                browser.close()
        manifest = {"schema_version": 1, "provenance": "OPERATOR_SUPPLIED_UNATTESTED",
                    "runtime_authenticated": False, "production_qualified": False,
                    "captures": captures}
        manifest_path = staging / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        manifest_path.chmod(0o600)
        # Manifest is published last; rollback any partial links on failure.
        publish_capture_set(staging, output_dir, SERVICES)
    return {"status": "CAPTURED_UNREVIEWED", "captures_performed": len(captures),
            "runtime_authenticated": False, "production_qualified": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--storage-state-dir", type=Path, required=True)
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    try:
        if args.plan.is_symlink():
            raise ValueError("symlink plan rejected")
        plan = json.loads(args.plan.read_text())
        print(json.dumps(capture(plan, args.output_dir, args.storage_state_dir,
                                 approved=args.capture), indent=2))
        return 0
    except (OSError, ValueError, ImportError) as exc:
        print("BLOCKED: " + str(exc), file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
