"""Operator-only export of one STAR run to a static HTML preview and JSON.

No external navigation, HTTP, browsers, GLPI/n8n/Grafana API calls or deployments.
The HTML is the *preview* of the same validated run as the JSON transport.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from demo.star_capture_evidence import verify_file
from demo.star_portal_html import render_storyboard
from demo.star_portal_storyboard import storyboard

def build_preview(manifest: Path, root: Path, scenario: str) -> tuple[dict, str]:
    report = verify_file(manifest, root)
    view = storyboard(report, scenario)
    document = {
        "schema": "star-portal-transport-v1",
        "run_id": report["run_id"],
        "scenario": scenario,
        "frames": view["frames"],
        "safety": {
            "read_only": True,
            "runtime_authenticated": False,
            "portal_integration_qualified": False,
            "remediation_authorized": False,
        },
    }
    return document, render_storyboard(report, scenario)

def export_preview(
    manifest: Path, root: Path, scenario: str, output_dir: Path
) -> tuple[Path, Path]:
    """Fail closed on existing output, including symlinks. No partial manifest/HTML."""
    document, page = build_preview(manifest, root, scenario)
    if output_dir.is_symlink():
        raise ValueError("symlink output directory forbidden")
    output_dir.mkdir(parents=True, exist_ok=True)
    if output_dir.is_symlink() or not output_dir.is_dir():
        raise ValueError("invalid output directory")
    dest_json = output_dir / "storyboard.json"
    dest_html = output_dir / "storyboard.html"
    if any(p.exists() or p.is_symlink() for p in (dest_json, dest_html)):
        raise FileExistsError("STAR preview already exists; refusing overwrite")
    created = []
    try:
        for target, content in (
            (dest_json, json.dumps(document, ensure_ascii=False, indent=2)),
            (dest_html, page),
        ):
            fd = os.open(str(target), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            created.append(target)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(content)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return dest_json, dest_html

def main() -> None:
    parser = argparse.ArgumentParser(description="Export an offline STAR preview")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--scenario", choices=("SAN_FABRIC_P1", "PAYMENTS_P2"), required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    export_preview(args.manifest, args.root, args.scenario, args.out)
    print("STAR_STATIC_PREVIEW_CREATED;NOT_DEPLOYED;NOT_RUNTIME_AUTHENTICATED")

if __name__ == "__main__":
    main()
