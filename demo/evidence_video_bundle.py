#!/usr/bin/env python3
"""Package verified operator captures as MP4 + SRT + hash receipt.

This is a packaging contract, NOT an authentication or LIVE attestation.
Unlike PR36's synthetic storyboard, no image or incident is invented here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

from demo.evidence_video import SERVICES, render, verify
from demo.evidence_snapshot import pin_captures

IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
NAMES = ("aiops-evidence.mp4", "aiops-evidence.srt", "aiops-evidence.receipt.json")
LABELS = {"portal": "Portail AIOps", "thruk": "Thruk", "grafana": "Grafana",
          "n8n": "n8n", "glpi": "GLPI"}


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timestamp(milliseconds: int) -> str:
    hours, rem = divmod(milliseconds, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def subtitles(captures: list[dict], seconds: int) -> str:
    """Only fixed, non-sensitive application labels; no incident text or URLs."""
    if not isinstance(seconds, int) or isinstance(seconds, bool) or not 2 <= seconds <= 20:
        raise ValueError("seconds must be 2..20")
    if [x.get("service") for x in captures] != list(SERVICES):
        raise ValueError("canonical five-scene order required")
    lines = []
    for index, item in enumerate(captures):
        start = index * seconds * 1000
        end = (index + 1) * seconds * 1000
        lines.append(f"{index + 1}\n{_timestamp(start)} --> {_timestamp(end)}\n"
                     f"{LABELS[item['service']]} — capture opérateur non attestée\n")
    return "\n".join(lines) + "\n"


def _correlation(manifest: dict) -> dict:
    entries = manifest["captures"]
    context = {}
    for field in ("run_id", "incident_id", "ticket_id", "session_label"):
        values = [item.get(field) for item in entries]
        if any(not isinstance(value, str) or not IDENT.fullmatch(value) for value in values):
            raise ValueError("missing or unsafe correlation field: " + field)
        if len(set(values)) != 1:
            raise ValueError("inconsistent correlation field: " + field)
        context[field] = values[0]
    for item in entries:
        url = item["source_url"]
        parsed = urlsplit(url)
        if parsed.query or parsed.fragment or any(c.isspace() for c in url) or "\\" in url:
            raise ValueError("source URL may expose secrets")
    return context


def _probe(video: Path, seconds: int) -> dict:
    ffprobe = shutil.which("ffprobe")
    ffmpeg = shutil.which("ffmpeg")
    if not ffprobe or not ffmpeg:
        raise RuntimeError("ffmpeg and ffprobe required")
    result = subprocess.run([ffprobe, "-v", "error", "-show_entries",
                             "format=duration:stream=codec_type,codec_name,width,height",
                             "-of", "json", str(video)], capture_output=True, text=True,
                            check=True, timeout=30)
    data = json.loads(result.stdout)
    duration = float(data["format"]["duration"])
    streams = [x for x in data["streams"] if x.get("codec_type") == "video"]
    if len(streams) != 1 or streams[0].get("codec_name") != "h264" or \
            (streams[0].get("width"), streams[0].get("height")) != (1920, 1080) or \
            not (5 * seconds - 0.25 <= duration <= 5 * seconds + 0.25):
        raise ValueError("invalid MP4 stream or duration")
    # Reuse the full decode check of PR36's video workflow, not just ffprobe metadata.
    subprocess.run([ffmpeg, "-v", "error", "-nostdin", "-i", str(video),
                    "-f", "null", "-"], capture_output=True, check=True, timeout=120)
    return {"duration_seconds": duration, "codec": "h264", "resolution": "1920x1080"}


def build_bundle(evidence_root: Path, manifest_path: Path, output_dir: Path, seconds: int = 6) -> dict:
    evidence_root, manifest_path, output_dir = map(Path, (evidence_root, manifest_path, output_dir))
    if not isinstance(seconds, int) or isinstance(seconds, bool) or not 2 <= seconds <= 20:
        raise ValueError("seconds must be 2..20")
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("regular manifest required")
    if output_dir.is_symlink() or not output_dir.is_dir() or \
            stat.S_IMODE(output_dir.stat().st_mode) & 0o077:
        raise ValueError("private existing output directory required (chmod 700)")
    if evidence_root.resolve() == output_dir.resolve():
        raise ValueError("evidence and output directories must differ")
    if any((output_dir / name).exists() or (output_dir / name).is_symlink() for name in NAMES):
        raise ValueError("refusing to overwrite existing output")
    # Reject duplicate JSON keys, as in PR36's STAR evidence manifest contract.
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)
    # First validation bounds paths/metadata; pin exact source bytes before
    # handing paths to FFmpeg, then reverify the pinned copies against hashes.
    captures = verify(evidence_root, manifest)
    context = _correlation(manifest)
    with tempfile.TemporaryDirectory(prefix=".evidence-bundle-", dir=output_dir) as td:
        stage = Path(td)
        pinned = pin_captures(evidence_root, stage, captures)
        captures = verify(pinned, manifest)
        srt = subtitles(captures, seconds)
        video = stage / NAMES[0]
        render(pinned, captures, video, seconds)
        video_info = _probe(video, seconds)
        video.chmod(0o600)
        captions = stage / NAMES[1]
        captions.write_text(srt, encoding="utf-8")
        captions.chmod(0o600)
        receipt = {
            "schema_version": 1,
            "provenance": "OPERATOR_SUPPLIED_UNATTESTED",
            "runtime_authenticated": False, "production_qualified": False,
            "capture_count": 5, "correlation": context,
            "captures": captures, "video": {"file": NAMES[0], "sha256": _sha(video), **video_info},
            "subtitles": {"file": NAMES[1], "sha256": _sha(captions)},
        }
        (stage / NAMES[2]).write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
        (stage / NAMES[2]).chmod(0o600)
        published = []
        try:
            for name in NAMES:
                # Atomic create-if-absent, no clobber even if another process races us.
                os.link(stage / name, output_dir / name)
                published.append(output_dir / name)
        except OSError:
            for path in published:
                path.unlink()
            raise
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=6)
    args = parser.parse_args()
    try:
        result = build_bundle(args.evidence_root, args.manifest, args.output_dir, args.seconds)
        print(json.dumps({"status": "BUNDLE_CREATED_UNATTESTED", "video": result["video"],
                          "subtitles": result["subtitles"], "runtime_authenticated": False}, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, KeyError, TypeError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
