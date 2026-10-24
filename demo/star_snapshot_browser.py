"""STAR read-only browser evidence collector (opt-in; never an operational executor).

Dry-run is the default. Even successful captures are UNREVIEWED and never attest
business state, DGX inference, approval, or LIVE remediation. Requires playwright
only for --capture; importing this module makes no network calls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from demo.star_snapshot_choreography import CUE_BY_NAME
from demo.star_capture_identity_guard import verify_snapshot_identity
from demo.star_browser_request_fence import ReadOnlyRequestPolicy

IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,95}$")
EVENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")
SELECTOR = re.compile(r"^[#\.\[A-Za-z][A-Za-z0-9_ #.\[\]='\"\-:>]*$")
MAX_SCREENSHOT = 20 * 1024 * 1024


@dataclass(frozen=True)
class CapturePlan:
    cue: str
    run_id: str
    correlation_id: str
    event_ref: str
    url: str
    expected_state: str
    identity_selector: str
    event_selector: str
    state_selector: str
    redact_selectors: tuple[str, ...]
    allowed_origin: str
    environment: str  # ISOLATED_TEST_FIXTURE or OPERATOR_BROWSER_UNREVIEWED
    correlation_selector: str  # exact DOM evidence; required even in fixture mode
    approved_get_urls: tuple[str, ...] = ()  # explicitly reviewed subresource GET URLs; none by default


def _origin(url: str) -> str:
    u = urlsplit(url)
    if (u.scheme not in ("http", "https") or not u.hostname or u.username is not None
            or u.password is not None or u.fragment or "\\" in url
            or any(c.isspace() for c in url) or u.hostname.endswith(".")):
        raise ValueError("unsafe URL")
    if u.netloc != u.netloc.lower() or u.port == 0:
        raise ValueError("noncanonical origin")
    return f"{u.scheme}://{u.netloc}"


def validate_plan(plan: CapturePlan) -> dict[str, str]:
    """Pure validation; no DNS resolution or HTTP request."""
    cue = CUE_BY_NAME.get(plan.cue)
    if cue is None:
        raise ValueError("unknown STAR cue")
    if not IDENTITY.fullmatch(plan.run_id) or not IDENTITY.fullmatch(plan.correlation_id):
        raise ValueError("missing/invalid run or correlation identity")
    if not EVENT.fullmatch(plan.event_ref):
        raise ValueError("invalid event identifier")
    if plan.expected_state != cue.required_state:
        raise ValueError("expected state not bound to cue")
    if plan.environment not in ("ISOLATED_TEST_FIXTURE", "OPERATOR_BROWSER_UNREVIEWED"):
        raise ValueError("invalid evidence provenance")
    origin = _origin(plan.url)
    if origin != plan.allowed_origin or _origin(plan.allowed_origin) != plan.allowed_origin:
        raise ValueError("source not on exact approved origin")
    u = urlsplit(plan.url)
    parts = u.path.split("/")
    if cue.service == "glpi":
        q = parse_qs(u.query, keep_blank_values=True)
        if (not plan.event_ref.isdigit() or not u.path.endswith("/front/ticket.form.php")
                or q != {"id": [plan.event_ref]}):
            raise ValueError("GLPI V1 ticket deep link mismatch")
        # Explicitly reject accidental GLPI 11 instance on :18080.
        if u.port != 8080:
            raise ValueError("GLPI V1 must be port 8080")
    elif cue.service == "n8n":
        # A deep link must terminate at the exact execution, not an arbitrary
        # path containing the ID followed by an unrelated view.
        if u.query or len(parts) < 3 or parts[-2] not in ("execution", "executions") or parts[-1] != plan.event_ref:
            raise ValueError("n8n execution deep link mismatch")
    elif cue.service == "grafana":
        if len(parts) < 3 or parts[1] != "d" or parts[2] != plan.event_ref:
            raise ValueError("Grafana dashboard deep link mismatch")
        # Optional fixed time window: never permit a default/relative Grafana
        # time window to masquerade as an event-aligned capture.
        if u.query:
            q = parse_qs(u.query, keep_blank_values=True)
            if set(q) != {"from", "to", "var-run_id"} or any(len(v) != 1 for v in q.values()):
                raise ValueError("Grafana event window query not canonical")
            start, end = q["from"][0], q["to"][0]
            if (not start.isascii() or not end.isascii() or not start.isdecimal() or not end.isdecimal()
                    or not (12 <= len(start) <= 16 and 12 <= len(end) <= 16)
                    or int(start) >= int(end) or int(end) - int(start) > 3_600_000
                    or q["var-run_id"] != [plan.run_id]):
                raise ValueError("Grafana event window or run identity mismatch")
        elif plan.environment != "ISOLATED_TEST_FIXTURE":
            raise ValueError("runtime Grafana capture requires fixed event window")
    else:
        raise ValueError("unsupported service")
    if (not isinstance(plan.approved_get_urls, tuple) or len(plan.approved_get_urls) > 32
            or len(set(plan.approved_get_urls)) != len(plan.approved_get_urls)):
        raise ValueError("invalid approved GET allowlist")
    for resource_url in plan.approved_get_urls:
        if (not isinstance(resource_url, str) or len(resource_url) > 2048
                or _origin(resource_url) != origin or resource_url == plan.url):
            raise ValueError("GET allowlist must contain unique exact same-origin subresource URLs")
    for selector in (plan.identity_selector, plan.correlation_selector, plan.event_selector, plan.state_selector, *plan.redact_selectors):
        if not isinstance(selector, str) or len(selector) > 150 or not SELECTOR.fullmatch(selector):
            raise ValueError("invalid DOM selector")
    if not plan.redact_selectors or len(plan.redact_selectors) > 20:
        raise ValueError("at least one explicit masking selector required")
    # A screenshot is not useful evidence if its required identity or state
    # labels are themselves masked. Also reject ambiguous proof selectors.
    proof_selectors = (plan.identity_selector, plan.correlation_selector,
                       plan.event_selector, plan.state_selector)
    if (len(set(proof_selectors)) != len(proof_selectors)
            or set(proof_selectors).intersection(plan.redact_selectors)):
        raise ValueError("redaction overlaps required checkpoint proof selectors")
    return {"cue": cue.cue, "service": cue.service, "view": cue.view,
            "required_state": cue.required_state, "origin": origin, "mode": "READ_ONLY_GET"}


def _safe_url(url: str, event_ref: str) -> str:
    """Persist only a known route *shape*, never a user-controlled path/slug.

    Route components can contain run IDs, tenant names and access tokens even
    when query strings and the nominal event ID have been removed.
    """
    u = urlsplit(url)
    if u.path.endswith("/front/ticket.form.php"):
        return "{origin}/front/ticket.form.php?{id_redacted}"
    if "/executions/" in u.path or "/execution/" in u.path:
        return "{origin}/{workflow_route_redacted}/executions/{event_ref}"
    if u.path.startswith("/d/"):
        return "{origin}/d/{dashboard_uid}/{slug_redacted}"
    return "{origin}/{path_redacted}"


def _write_new(path: Path, content: bytes) -> None:
    """Atomic create-only write; no symlink following or silent overwrite."""
    if path.exists() or path.is_symlink():
        raise ValueError("evidence target already exists")
    fd, temp = tempfile.mkstemp(prefix=".star-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        # Create-only via hard link: unlike os.replace, refuses existing target.
        os.link(temp, path, follow_symlinks=False)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def capture(plan: CapturePlan, output_dir: Path, *, approved_read: bool = False,
            fixture_html: str | None = None) -> dict[str, object]:
    """Capture one exact event page, blocking non-GET/cross-origin requests.

    This method does not authenticate business outcomes. Any blocked request,
    missing ID/state or absent mask makes the capture fail without output.
    """
    meta = validate_plan(plan)
    if fixture_html is not None and plan.environment != "ISOLATED_TEST_FIXTURE":
        raise ValueError("fixture HTML forbidden outside isolated test")
    # GitHub Actions and local offline qualification must never be able to
    # browse an operator/runtime origin, even with --capture accidentally set.
    if os.environ.get("AIOPS_STAR_NO_RUNTIME") == "1" and approved_read and (
            fixture_html is None or plan.environment != "ISOLATED_TEST_FIXTURE"):
        raise ValueError("runtime browsing disabled in offline qualification")
    if not approved_read:
        return {"result": "DRY_RUN", "cue": plan.cue, "service": meta["service"],
                "runtime_authenticated": False, "effects": "NONE"}
    # Operator browsing is a separate, deliberate authorization boundary.
    # --capture alone must not make an unreviewed plan contact any runtime.
    if (fixture_html is None and
            os.environ.get("AIOPS_STAR_ALLOW_OPERATOR_READ") != "1"):
        raise ValueError("operator runtime browsing requires explicit environment opt-in")
    from playwright.sync_api import sync_playwright

    root = Path(output_dir)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("output directory must already exist and not be symlink")
    if plan.environment == "OPERATOR_BROWSER_UNREVIEWED" and meta["origin"].startswith("http://"):
        # Internal HTTP may be approved for legacy V1, but never claim secure transport.
        pass
    policy = ReadOnlyRequestPolicy(plan.url, plan.allowed_origin, plan.approved_get_urls)
    policy.validate()
    blocked: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=(os.getenv("AIOPS_CHROMIUM_PATH") or shutil.which("chromium") or None))
        try:
            context = browser.new_context(service_workers="block", accept_downloads=False,
                                          permissions=[], viewport={"width": 1440, "height": 900})
            context.set_default_timeout(8000)
            if hasattr(context, "route_web_socket"):
                context.route_web_socket("**/*", lambda ws: (blocked.append("websocket"), ws.close()))

            def route_handler(route):
                req = route.request
                try:
                    # set_content() is a purely local fixture. It must never
                    # contact even an otherwise allowlisted operator origin.
                    # Pure request filter is independently tested and
                    # shared by the offline adapter contract.
                    allowed = (fixture_html is None and policy.permits(
                        url=req.url, method=req.method,
                        navigation=req.is_navigation_request(),
                        main_frame=(req.frame == page.main_frame),
                        resource_type=req.resource_type))
                except ValueError:
                    allowed = False
                if allowed:
                    route.continue_()
                else:
                    blocked.append("denied-request")
                    route.abort()

            context.route("**/*", route_handler)
            page = context.new_page()
            context.on("page", lambda new_page: blocked.append("unexpected-popup") if new_page != page else None)
            page.on("pageerror", lambda _: blocked.append("javascript-error"))
            page.on("download", lambda _: blocked.append("download-attempt"))
            if fixture_html is not None:
                page.set_content(fixture_html, wait_until="domcontentloaded")
            else:
                response = page.goto(plan.url, wait_until="domcontentloaded", timeout=12000)
                if not response or response.status != 200 or _origin(page.url) != meta["origin"]:
                    raise ValueError("wrong runtime page/HTTP status")
                if urlsplit(page.url).path != urlsplit(plan.url).path or urlsplit(page.url).query != urlsplit(plan.url).query:
                    raise ValueError("redirect changed event identity")
            page.wait_for_timeout(300)  # bounded observation of asynchronous page requests
            if blocked:
                raise ValueError("page attempted non-read-only or external network activity")

            def required_text(selector: str) -> str:
                locator = page.locator(selector)
                if locator.count() != 1 or not locator.is_visible():
                    raise ValueError("required event DOM element missing or ambiguous")
                # Playwright is_visible() checks geometry/visibility, NOT CSS
                # opacity or transparent text. Such DOM values can be correct
                # while the screenshot contains no legible proof at all.
                # Check the element and every ancestor before trusting text.
                painted = locator.evaluate(r"""el => {
                    const color = getComputedStyle(el).color.toLowerCase().replace(/\s/g, '');
                    if (color === 'transparent') return false;
                    const rgba = color.match(/^rgba?\(([^)]*)\)$/);
                    if (rgba) {
                        const parts = rgba[1].split(',');
                        if (parts.length === 4 && Number(parts[3]) <= 0.05) return false;
                        const slash = rgba[1].split('/');
                        if (slash.length === 2 && Number(slash[1]) <= 0.05) return false;
                    }
                    if (parseFloat(getComputedStyle(el).fontSize) <= 0) return false;
                    // CSS paint suppression can leave innerText and is_visible()
                    // unchanged while removing every proof pixel from the PNG.
                    // Reject uncertain clipping/filter/masking on the entire
                    // proof ancestry instead of asserting that it is legible.
                    const transparent = value => {
                        const v = String(value || '').toLowerCase().replace(/\s/g, '');
                        if (v === 'transparent') return true;
                        const rgba = v.match(/^rgba?\(([^)]*)\)$/);
                        if (!rgba) return false;
                        const parts = rgba[1].split(',');
                        if (parts.length === 4 && Number(parts[3]) <= 0.05) return true;
                        const slash = rgba[1].split('/');
                        return slash.length === 2 && Number(slash[1]) <= 0.05;
                    };
                    if (transparent(getComputedStyle(el).webkitTextFillColor)) return false;
                    for (let node = el; node && node.nodeType === 1; node = node.parentElement) {
                        const style = getComputedStyle(node);
                        const opacity = Number(style.opacity);
                        if (!Number.isFinite(opacity) || opacity <= 0.05) return false;
                        if (style.filter !== 'none' || style.clipPath !== 'none' ||
                            style.webkitClipPath !== 'none' || style.maskImage !== 'none' ||
                            style.webkitMaskImage !== 'none') return false;
                    }
                    return true;
                }""")
                if not painted:
                    raise ValueError("visually hidden checkpoint proof")
                return locator.inner_text(timeout=4000).strip()

            verify_snapshot_identity(
                {"run_id": plan.run_id, "correlation_id": plan.correlation_id,
                 "event_ref": plan.event_ref},
                {"run_id": required_text(plan.identity_selector),
                 "correlation_id": required_text(plan.correlation_selector),
                 "event_ref": required_text(plan.event_selector)},
            )
            observed_state = required_text(plan.state_selector)
            if observed_state != plan.expected_state:
                raise ValueError("observed state contradicts requested cue")
            masks = []
            proof_selectors = (plan.identity_selector, plan.correlation_selector,
                               plan.event_selector, plan.state_selector)
            for selector in plan.redact_selectors:
                locator = page.locator(selector)
                if locator.count() < 1 or not locator.first.is_visible():
                    raise ValueError("required redaction element missing")
                # Even distinct selectors can overlap in the DOM: masking an
                # ancestor (e.g. #app/body), descendant or CSS-positioned
                # sibling can conceal the exact run/event/state. Masked pixels
                # must not overlap any required proof rectangle. Fail closed.
                hides_proof = locator.evaluate_all(
                    """(masks, selectors) => {
                        const overlaps = (a, b) => {
                            const x = a.getBoundingClientRect();
                            const y = b.getBoundingClientRect();
                            return x.width > 0 && x.height > 0 &&
                                   y.width > 0 && y.height > 0 &&
                                   x.left < y.right && y.left < x.right &&
                                   x.top < y.bottom && y.top < x.bottom;
                        };
                        return selectors.some(selector =>
                            [...document.querySelectorAll(selector)].some(proof =>
                                masks.some(mask => mask.contains(proof) ||
                                    proof.contains(mask) || overlaps(mask, proof))));
                    }""",
                    list(proof_selectors),
                )
                if hides_proof:
                    raise ValueError("redaction DOM region conceals checkpoint proof")
                masks.append(locator)
            screenshot = page.screenshot(full_page=True, animations="disabled", mask=masks, mask_color="#000000")
            if blocked or (fixture_html is None and page.url != plan.url):
                raise ValueError("unsafe network activity or page navigation during capture")
            if len(screenshot) > MAX_SCREENSHOT or not screenshot.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("invalid screenshot payload")
            stamp = datetime.now(timezone.utc).isoformat()
        finally:
            browser.close()
    digest = hashlib.sha256(screenshot).hexdigest()
    basename = f"{plan.cue}-{hashlib.sha256((plan.run_id+plan.event_ref).encode()).hexdigest()[:16]}"
    screenshot_path = root / (basename + ".png")
    manifest_path = root / (basename + ".json")
    if screenshot_path.exists() or manifest_path.exists():
        raise ValueError("evidence already exists; never overwrite")
    manifest = {"schema": "star-browser-evidence/v1", "cue": plan.cue,
                "service": meta["service"], "view": meta["view"],
                "run_id": plan.run_id, "correlation_id": plan.correlation_id,
                "event_ref": plan.event_ref, "expected_state": plan.expected_state,
                "observed_state": observed_state, "captured_at": stamp,
                "source_url_redacted": _safe_url(plan.url, plan.event_ref),
                "sha256": digest, "screenshot_file": screenshot_path.name,
                "provenance": plan.environment,
                "anonymization": "SELECTOR_MASKS_UNREVIEWED",
                "event_time_alignment": "UNVERIFIED_REQUIRES_EXTERNAL_EVENT_TIMESTAMP",
                "capture_transport": "LOCAL_HTML_FIXTURE_NO_HTTP" if fixture_html is not None else "READ_ONLY_BROWSER_HTTP_GET",
                "runtime_page_authenticated": False,
                "business_outcome_verified": False,
                "human_approval_authenticated": False,
                "qualification": "CAPTURED_UNREVIEWED_NOT_BUSINESS_PROOF"}
    _write_new(screenshot_path, screenshot)
    try:
        _write_new(manifest_path, (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)+"\n").encode())
    except Exception:
        screenshot_path.unlink(missing_ok=True)
        raise
    return {"result": "CAPTURED_UNREVIEWED", "manifest": manifest_path.name,
            "sha256": digest, "runtime_authenticated": False}


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate capture plan JSON key")
        result[key] = value
    return result


def load_plan(path: Path) -> CapturePlan:
    if path.stat().st_size > 16_384:
        raise ValueError("capture plan exceeds size limit")
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    allowed = set(CapturePlan.__dataclass_fields__)
    required = allowed - {"approved_get_urls"}
    if not isinstance(data, dict) or not required <= set(data) or set(data) - allowed:
        raise ValueError("capture plan fields missing or unexpected")
    if not isinstance(data["redact_selectors"], list):
        raise ValueError("redact_selectors must be a list")
    if not isinstance(data.get("approved_get_urls", []), list):
        raise ValueError("approved_get_urls must be a list")
    data["redact_selectors"] = tuple(data["redact_selectors"])
    data["approved_get_urls"] = tuple(data.get("approved_get_urls", []))
    return CapturePlan(**data)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only STAR capture; dry-run by default")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--capture", action="store_true", help="explicitly authorize read-only browser GETs")
    args = parser.parse_args(argv)
    try:
        plan = load_plan(args.plan)
        if args.capture and args.output_dir is None:
            raise ValueError("capture requires existing output directory")
        result = capture(plan, args.output_dir or Path("."), approved_read=args.capture)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["result"] in ("DRY_RUN", "CAPTURED_UNREVIEWED") else 2
    except Exception as exc:
        # No exception details: may contain URLs, credentials or sensitive data.
        print(json.dumps({"result": "REJECTED", "error_class": type(exc).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
