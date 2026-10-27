"""Read-only STAR transport document for the existing :17777 portal.

Emit JSON only. This is not a FastAPI route or a screenshot capture service.
The deployer must explicitly integrate the returned data into the existing portal.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from demo.star_capture_evidence import verify_file
from demo.star_portal_storyboard import storyboard

def export_storyboard(manifest: Path, root: Path, scenario: str) -> dict:
    report = verify_file(manifest, root)
    view = storyboard(report, scenario)
    # Keep this surface independent from direct app URL access and raw secrets.
    return {
        "schema": "star-portal-transport-v1",
        "run_id": report["run_id"],
        "scenario": view["scenario"],
        "frames": view["frames"],
        "safety": {
            "read_only": True, "runtime_authenticated": False,
            "portal_integration_qualified": False,
            "remediation_authorized": False,
        },
    }

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("manifest", type=Path)
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--scenario", required=True, choices=["SAN_FABRIC_P1","PAYMENTS_P2"])
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    document = export_storyboard(args.manifest, args.root, args.scenario)
    # Fail-closed: never overwrite another file or follow a symlink.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2)
    print("STAR_EXPORT_CREATED;PROVENANCE_UNAUTHENTICATED;NO_LIVE_ACTION")

if __name__ == "__main__":
    main()
