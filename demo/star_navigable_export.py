"""Generate a navigable STAR HTML page and transport JSON from one manifest.

This is an offline operator command, NOT an endpoint on the deployed :17777 portal.
No live calls, no arbitrary assets, and no overwrites.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from demo.star_portal_export import build_preview
from demo.star_navigable_preview import render_navigator

def export_navigable(manifest: Path, root: Path, scenario: str, output: Path) -> tuple[Path, Path]:
    document, _ = build_preview(manifest, root, scenario)
    page = render_navigator(document, scenario)
    if output.is_symlink():
        raise ValueError("symlink output directory")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not output.is_dir() or output.is_symlink():
        raise ValueError("invalid output directory")
    files = ((output / "star-scenes.json", json.dumps(document, ensure_ascii=False, indent=2)),
             (output / "star-scenes.html", page))
    if any(p.exists() or p.is_symlink() for p, _ in files):
        raise FileExistsError("STAR file already exists")
    created = []
    try:
        for path, content in files:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(path)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(content)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return files[0][0], files[1][0]

def main() -> None:
    parser = argparse.ArgumentParser(description="Offline STAR navigable preview")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--scenario", choices=("SAN_FABRIC_P1", "PAYMENTS_P2"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    export_navigable(args.manifest, args.root, args.scenario, args.out)
    print("STAR_NAVIGABLE_PREVIEW_CREATED;NOT_DEPLOYED;READ_ONLY")

if __name__ == "__main__":
    main()
