#!/usr/bin/env python3
"""Build one video from operator-supplied PNG screenshots, never claim live attestation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import zlib
from datetime import datetime, timezone
from urllib.parse import urlsplit
import subprocess
import sys
import tempfile

SERVICES = ("portal", "thruk", "grafana", "n8n", "glpi")
PNG = bytes.fromhex("89504e470d0a1a0a")

def valid_png(data):
    """Check PNG chunk bounds, CRC and terminal IEND, without decoding pixels."""
    if not data.startswith(PNG):
        return False
    offset = len(PNG)
    seen_ihdr = False
    seen_idat = False
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset:offset + 4], "big")
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + length
        if length > 20 * 1024 * 1024 or end > len(data):
            return False
        payload = data[offset + 8:offset + 8 + length]
        checksum = int.from_bytes(data[offset + 8 + length:end], "big")
        if zlib.crc32(kind + payload) & 0xffffffff != checksum:
            return False
        if not seen_ihdr:
            if kind != b"IHDR" or length != 13:
                return False
            seen_ihdr = True
        elif kind == b"IHDR":
            return False
        if kind == b"IDAT":
            seen_idat = True
        if kind == b"IEND":
            return length == 0 and seen_idat and end == len(data)
        offset = end
    return False

def decoded_png_scanlines(data):
    """Bounded PNG pixel-stream check; not visual inspection or runtime attestation.

    Only non-interlaced RGB/RGBA 8-bit PNG is accepted: the formats used for
    Playwright screenshots. Reject compressed bombs, hidden text and malformed
    zlib streams before FFmpeg receives any evidence.
    """
    if not valid_png(data):
        return False
    width = height = channels = None
    offset = len(PNG)
    idats = []
    idat_finished = False
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset:offset + 4], "big")
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        offset += 12 + length
        if kind in (b"tEXt", b"zTXt", b"iTXt", b"eXIf"):
            return False
        if kind[0] & 32 == 0 and kind not in (b"IHDR", b"PLTE", b"IDAT", b"IEND"):
            return False
        if kind == b"IHDR":
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            if depth != 8 or color not in (2, 6) or compression or filtering or interlace:
                return False
            channels = 3 if color == 2 else 4
        elif kind == b"IDAT":
            if idat_finished:
                return False
            idats.append(payload)
        elif idats:
            idat_finished = True
    if not idats or width is None:
        return False
    stride = width * channels + 1
    expected = stride * height
    if expected > 32 * 1024 * 1024:
        return False
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(b"".join(idats), expected + 1)
        if (len(raw) != expected or not decoder.eof or decoder.unconsumed_tail
                or decoder.unused_data or decoder.flush()):
            return False
    except zlib.error:
        return False
    return all(raw[row * stride] <= 4 for row in range(height))

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
    first_capture = previous_capture = None
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
        # A receipt must not relabel one application's PNG as another view.
        # This is a structural identity gate, not proof of screenshot origin.
        if rel != service + ".png":
            raise ValueError("service screenshot filename mismatch")
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
        if not decoded_png_scanlines(data):
            raise ValueError('invalid PNG chunks, pixels, metadata or CRC')
        digest = hashlib.sha256(data).hexdigest()
        if entry.get("sha256") != digest:
            raise ValueError("screenshot checksum mismatch")
        try:
            stamp = entry["captured_at_utc"]
            dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if not stamp.endswith("Z") or dt.tzinfo != timezone.utc:
                raise ValueError()
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ValueError("valid UTC timestamp required")
        # A five-view bundle must represent one short, ordered capture session.
        # These are operator-declared timestamps, NOT authenticated clock evidence.
        if previous_capture is not None and dt < previous_capture:
            raise ValueError("capture timestamps must be nondecreasing")
        if first_capture is not None and (dt - first_capture).total_seconds() > 15 * 60:
            raise ValueError("capture session exceeds 15-minute window")
        if first_capture is None:
            first_capture = dt
        previous_capture = dt
        url = entry.get("source_url")
        if not isinstance(url, str):
            raise ValueError("source URL required")
        try:
            parsed = urlsplit(url)
            hostname, port = parsed.hostname, parsed.port
        except ValueError as exc:
            raise ValueError("source URL may expose secrets or be unsafe") from exc
        if (parsed.scheme not in ("http", "https") or not hostname or
                parsed.username is not None or parsed.password is not None or
                "?" in url or "#" in url or "\\" in url or
                any(c.isspace() for c in url) or
                parsed.netloc != parsed.netloc.lower() or hostname.endswith(".") or port == 0 or
                ".." in parsed.path.split("/")):
            raise ValueError("source URL may expose secrets or be unsafe")
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
    if output.exists() or output.is_symlink():
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
        concat.write_text("".join("file '" + str(p) + "'\n" for p in clips))
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
