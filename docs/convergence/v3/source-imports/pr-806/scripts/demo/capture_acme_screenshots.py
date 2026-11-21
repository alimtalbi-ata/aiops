#!/usr/bin/env python3
"""Read-only ACME Portal screenshot capture. Never invents missing evidence.

Requires explicit deployed SHA, sandbox localhost target and verified scene routes.
Does not perform login, click, POST, or state-changing actions.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit, urljoin

import yaml
from playwright.sync_api import sync_playwright

DEFAULT_CONFIG = Path("scripts/demo/scenes.yaml")
DEFAULT_META = Path("docs/demo/evidence/ACME-SAN-PAYMENTS/meta.json")
SHA_PATTERN = re.compile(r"[0-9a-fA-F]{40}")

def config_from(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    def replace(match):
        expr = match.group(1)
        name, _, fallback = expr.partition(":-")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            raise ValueError("Invalid environment variable name in config")
        return os.environ.get(name, fallback)
    config = yaml.safe_load(re.sub(r"\$\{([^}]+)\}", replace, raw))
    if not isinstance(config, dict) or not isinstance(config.get("scenes"), list):
        raise ValueError("Invalid scene configuration")
    return config

def validate_config(config: dict, sha: str, allow_remote: bool) -> tuple[str, Path]:
    if not SHA_PATTERN.fullmatch(sha):
        raise ValueError("DEPLOYED_SHA must be the exact 40-character deployed Git SHA")
    base = config.get("base_url", "")
    parsed = urlsplit(base)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Invalid Portal base URL")
    if not allow_remote and (parsed.hostname not in ("localhost", "127.0.0.1", "::1") or parsed.scheme != "http"):
        raise ValueError("Only local HTTP Portal allowed by default; --allow-remote requires review")
    output = Path(config.get("output_dir", ""))
    if not str(output) or output.is_absolute() or ".." in output.parts:
        raise ValueError("Output must be a relative repository path")
    scenes = config["scenes"]
    if len(scenes) != 8:
        raise ValueError("Expected 7 mandatory scenes and 1 optional scene")
    seen_ids, seen_files = set(), set()
    for scene in scenes:
        sid = str(scene.get("id", ""))
        name = scene.get("file", "")
        route = scene.get("path", "")
        if sid not in {f"{i:02d}" for i in range(1, 9)} or sid in seen_ids:
            raise ValueError("Invalid or duplicate scene ID")
        if not isinstance(name, str) or not re.fullmatch(r"[0-9]{2}-[a-z0-9-]+\.png", name) or name in seen_files:
            raise ValueError("Invalid or duplicate screenshot filename")
        if not isinstance(route, str) or not route.startswith("/") or route.startswith("//") or "?" in route or "#" in route:
            if not (sid == "08" and scene.get("optional") and route == "NOT_IMPLEMENTED"):
                raise ValueError(f"Scene {sid}: route NOT_IMPLEMENTED or unsafe")
        if not isinstance(scene.get("wait_for"), str) or not scene["wait_for"].strip():
            raise ValueError(f"Scene {sid}: missing selector")
        if sid != "08" and scene.get("optional"):
            raise ValueError("Only scene 08 may be optional")
        seen_ids.add(sid)
        seen_files.add(name)
    if seen_ids != {f"{i:02d}" for i in range(1, 9)}:
        raise ValueError("Missing scene IDs")
    return base.rstrip("/"), output

def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--meta-out", type=Path, default=DEFAULT_META)
    parser.add_argument("--run-id", default=os.environ.get("ACME_RUN_ID", ""))
    parser.add_argument("--deployed-sha", default=os.environ.get("DEPLOYED_SHA", ""))
    parser.add_argument("--allow-remote", action="store_true", help="Explicitly allow reviewed non-local Portal")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)
    try:
        cfg = config_from(args.config)
        base, out = validate_config(cfg, args.deployed_sha, args.allow_remote)
        viewport = cfg.get("viewport", {"width": 1600, "height": 900})
        if viewport != {"width": 1600, "height": 900}:
            raise ValueError("Evidence capture requires 1600x900 viewport")
        if args.run_id and not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", args.run_id):
            raise ValueError("Invalid run-id")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"PRECHECK FAILED: {exc}", file=sys.stderr)
        return 2

    results = []
    failures = 0
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed)
        context = browser.new_context(viewport=viewport, device_scale_factor=1, accept_downloads=False)
        page = context.new_page()
        for scene in cfg["scenes"]:
            sid = str(scene["id"])
            route = scene["path"]
            name = scene["file"]
            target = out / name
            target.unlink(missing_ok=True)  # never retain stale PASS artifacts
            entry = {"id": sid, "scene": scene.get("name", sid), "file": f"screenshots/{name}", "status": "FAIL"}
            try:
                if route == "NOT_IMPLEMENTED":
                    raise ValueError("NOT_IMPLEMENTED: no confirmed Portal route")
                route = route.replace("{run_id}", args.run_id)
                if "{run_id}" in route or not route.startswith("/"):
                    raise ValueError("Missing run-id or invalid route")
                url = urljoin(base + "/", route.lstrip("/"))
                if urlsplit(url).netloc != urlsplit(base).netloc:
                    raise ValueError("Cross-origin scene route")
                response = page.goto(url, wait_until="domcontentloaded", timeout=20000)
                if response is None or response.status >= 400:
                    raise ValueError("Portal HTTP error or no response")
                if urlsplit(page.url).netloc != urlsplit(base).netloc:
                    raise ValueError("Unexpected cross-origin redirect")
                page.locator(scene["wait_for"]).wait_for(state="visible", timeout=10000)
                body = page.locator("body").inner_text(timeout=10000)
                if cfg.get("mode_banner_must_contain", "SIMULATION") not in body:
                    raise ValueError("SIMULATION banner missing")
                for expected in scene.get("assert_text", []):
                    if expected not in body:
                        raise ValueError("Required scene text missing")
                page.screenshot(path=str(target), full_page=False, animations="disabled")
                entry["status"] = "PASS"
                print(f"PASS {sid}: {target}")
            except Exception as exc:
                # Avoid logging URLs, page contents, cookies, or tokens.
                entry["status"] = "NOT_IMPLEMENTED" if route == "NOT_IMPLEMENTED" else "FAIL"
                entry["error_type"] = type(exc).__name__
                if not scene.get("optional"):
                    failures += 1
                print(f"{entry['status']} {sid}", file=sys.stderr)
            results.append(entry)
        browser.close()
    meta = {
        "scenario_id": "ACME-SAN-PAYMENTS", "tenant_id": "ACME-TEST",
        "mode": "SIMULATION", "deployed_sha": args.deployed_sha.lower(),
        "run_id": args.run_id or None,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if failures == 0 else "FAIL",
        "screenshots": results,
        "notes": "Automated read-only sandbox capture; no LIVE claims.",
    }
    args.meta_out.parent.mkdir(parents=True, exist_ok=True)
    args.meta_out.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return 0 if failures == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
