#!/usr/bin/env python3
"""Build one video from operator-supplied PNG screenshots, never claim live attestation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

SERVICES = ("portal", "thruk", "grafana", "n8n", "glpi")
PNG = bytes.fromhex("89504e470d0a1a0a")

def verify(root, manifest):
    if root.is_symlink() or not root.is_dir():
        raise ValueError("evidence root must be a real directory")
    if manifest.get("schema_version") != 1 or manifest.get("provenance") != "OPERATOR_SUPPLIED_UNATTESTED":
        raise ValueError("invalid provenance or schema")
    entries = manifest.get("captures")
    if not isinstance(entries, list) or len(entries) != len(SERVICES):
        raise ValueError("exactly five service captures required")
    result = []
    seen = set()
    for entry in entries:
        service = entry.get("service")
        if service not in SERVICES or service in seen:
            raise ValueError("missing, unknown or repeated service")
        seen.add(service)
        rel = entry.get("file")
        if not isinstance(rel, str) or not rel.endswith(".png"):
            raise ValueError("PNG relative file required")
        path = Path(rel)
        if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
            raise ValueError("unsafe screenshot path")
        actual = root / path
        if actual.is_symlink() or not actual.is_file():
            raise ValueError("missing screenshot or symlink")
        size = actual.stat().st_size
        if not 32 <= size <= 20 * 1024 * 1024:
            raise ValueError("invalid PNG size")
        with actual.open("rb") as f:
            head = f.read(24)
        if not head.startswith(PNG) or head[12:16] != b"IHDR":
            raise ValueError("invalid PNG header")
        width, height = struct.unpack(">II", head[16:24])
        if not (200 <= width <= 10000 and 200 <= height <= 10000 and width * height <= 40000000):
            raise ValueError("unsafe PNG dimensions")
        data = actual.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if entry.get("sha256") != digest:
            raise ValueError("screenshot checksum mismatch")
        if not isinstance(entry.get("captured_at_utc"), str) or not entry["captured_at_utc"].endswith("Z"):
            raise ValueError("capture UTC timestamp required")
        if not isinstance(entry.get("source_url"), str) or not entry["source_url"].startswith(("http://", "https://")):
            raise ValueError("source URL required")
        result.append({"service": service, "file": rel, "sha256": digest,
                       "source_url": entry["source_url"], "captured_at_utc": entry["captured_at_utc"],
                       "status": "BYTES_HASH_VERIFIED_NOT_RUNTIME_ATTESTED"})
    if seen != set(SERVICES):
        raise ValueError("all five services required")
    return result

def render(root, captures, output, seconds):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg required")
    if output.exists():
        raise ValueError("refusing to overwrite video")
    with tempfile.TemporaryDirectory(prefix="aiops-evidence-video-") as td:
        clips = []
        for i, item in enumerate(captures):
            clip = Path(td) / f"{i:02}.mp4"
            source = root / item["file"]
            vf = ("scale=1920:1080:force_original_aspect_ratio=decrease,"
                  "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
                  "format=yuv420p")
            subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
                            "-loop", "1", "-framerate", "25", "-i", str(source),
                            "-t", str(seconds), "-vf", vf, "-r", "25",
                            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                            "-y", str(clip)], check=True)
            clips.append(clip)
        concat = Path(td) / "concat.txt"
        concat.write_text("".join("file '" + str(p) + "'\\n" for p in clips))
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
                        "-f", "concat", "-safe", "0", "-i", str(concat),
                        "-c", "copy", "-movflags", "+faststart", str(output)], check=True)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--evidence-root", required=True, type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--seconds", type=int, default=6)
    a = p.parse_args()
    if not 2 <= a.seconds <= 20:
        p.error("seconds must be 2..20")
    try:
        if a.manifest.is_symlink() or not a.manifest.is_file():
            raise ValueError("manifest must be a regular file")
        captures = verify(a.evidence_root, json.loads(a.manifest.read_text()))
        if a.output:
            render(a.evidence_root, captures, a.output, a.seconds)
        print(json.dumps({"status": "VIDEO_CREATED" if a.output else "CAPTURES_VALIDATED",
                          "provenance": "OPERATOR_SUPPLIED_UNATTESTED",
                          "runtime_authenticated": False, "production_qualified": False,
                          "captures": captures, "video": str(a.output) if a.output else None}, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
