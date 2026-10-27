#!/usr/bin/env python3
"""Verify STAR screenshot bytes and metadata without contacting applications.

A verified hash proves only that the manifest matches the local bytes. It does
not authenticate the application, session, business state, or runtime event.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import zlib
from typing import Any
from urllib.parse import urlsplit

from demo.star_snapshot_choreography import CUES

MAX_SCREENSHOT_BYTES = 20 * 1024 * 1024
MAX_PNG_DIMENSION = 30_000
MAX_PNG_PIXELS = 100_000_000
MAX_PNG_DECODED_BYTES = 128 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _utc_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    # The field is explicitly named *_utc: accept only UTC (Z or +00:00),
    # not merely any timezone-aware local timestamp.
    return parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0)


def _origin(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError("unsafe source URL")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid source URL port") from exc
    host = parsed.hostname.lower()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"{parsed.scheme.lower()}://{host}" + (f":{port}" if port is not None else "")


def _safe_file(root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative or "%" in relative:
        raise ValueError("invalid relative screenshot path")
    candidate = Path(relative)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValueError("invalid relative screenshot path")
    current = root
    for part in candidate.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("symlink in screenshot path")
    resolved = current.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError("screenshot escapes evidence root")
    info = resolved.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("screenshot must be a regular file")
    if info.st_size <= 0 or info.st_size > MAX_SCREENSHOT_BYTES:
        raise ValueError("screenshot size outside permitted bounds")
    return resolved


def _verify_png(path: Path) -> dict[str, int]:
    """Verify PNG framing, CRCs and bounded zlib scanlines without rendering pixels."""
    raw = path.read_bytes()
    if not raw.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG image")
    offset = len(PNG_SIGNATURE)
    chunk_index = 0
    dimensions: tuple[int, int] | None = None
    bit_depth: int | None = None
    color_type: int | None = None
    saw_iend = False
    saw_idat = False
    idat_ended = False
    saw_plte = False
    compressed_parts: list[bytes] = []
    allowed_depths = {0: {1, 2, 4, 8, 16}, 2: {8, 16}, 3: {1, 2, 4, 8}, 4: {8, 16}, 6: {8, 16}}
    while offset < len(raw):
        if len(raw) - offset < 12:
            raise ValueError("truncated PNG chunk")
        length = struct.unpack(">I", raw[offset:offset + 4])[0]
        chunk_type = raw[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(raw):
            raise ValueError("PNG chunk exceeds file bounds")
        data = raw[offset + 8:offset + 8 + length]
        expected_crc = struct.unpack(">I", raw[offset + 8 + length:end])[0]
        if zlib.crc32(chunk_type + data) & 0xFFFFFFFF != expected_crc:
            raise ValueError("PNG chunk CRC mismatch")

        if chunk_index == 0:
            if chunk_type != b"IHDR" or length != 13:
                raise ValueError("PNG must start with a valid IHDR")
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(">IIBBBBB", data)
            if (
                width < 1 or height < 1
                or width > MAX_PNG_DIMENSION or height > MAX_PNG_DIMENSION
                or width * height > MAX_PNG_PIXELS
            ):
                raise ValueError("PNG dimensions outside permitted bounds")
            if color_type not in allowed_depths or bit_depth not in allowed_depths[color_type]:
                raise ValueError("unsupported PNG color type or bit depth")
            if compression != 0 or filtering != 0 or interlace != 0:
                raise ValueError("only standard non-interlaced PNG images are accepted")
            dimensions = (width, height)
        elif chunk_type == b"IHDR":
            raise ValueError("duplicate PNG IHDR")

        if chunk_type == b"PLTE":
            if saw_plte or saw_idat or color_type in {0, 4} or length == 0 or length % 3 or length > 768:
                raise ValueError("invalid PNG palette")
            if color_type == 3 and length // 3 > 2 ** bit_depth:
                raise ValueError("PNG palette exceeds indexed bit depth")
            saw_plte = True

        if chunk_type == b"IDAT":
            if idat_ended:
                raise ValueError("PNG IDAT chunks must be consecutive")
            if color_type == 3 and not saw_plte:
                raise ValueError("indexed PNG is missing its palette")
            saw_idat = True
            compressed_parts.append(data)
        elif saw_idat:
            idat_ended = True

        # Unknown critical chunks are not safe to silently skip.
        if chunk_type not in {b"IHDR", b"PLTE", b"IDAT", b"IEND"} and chunk_type[0] & 0x20 == 0:
            raise ValueError("unsupported critical PNG chunk")

        if chunk_type == b"IEND":
            if length != 0 or not saw_idat:
                raise ValueError("invalid PNG IEND or missing IDAT")
            saw_iend = True
            offset = end
            break
        offset = end
        chunk_index += 1

    if not saw_iend or not saw_idat or offset != len(raw) or dimensions is None or bit_depth is None or color_type is None:
        raise ValueError("incomplete PNG or trailing bytes")

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    row_bytes = (dimensions[0] * channels * bit_depth + 7) // 8
    expected_decoded_bytes = (row_bytes + 1) * dimensions[1]
    if expected_decoded_bytes > MAX_PNG_DECODED_BYTES:
        raise ValueError("decoded PNG data exceeds verification limit")

    decoder = zlib.decompressobj()
    try:
        decoded = decoder.decompress(b"".join(compressed_parts), expected_decoded_bytes + 1)
        if len(decoded) > expected_decoded_bytes or decoder.unconsumed_tail:
            raise ValueError("PNG decompressed data exceeds expected scanline size")
        if not decoder.eof:
            raise ValueError("truncated PNG compressed image data")
        if decoder.unused_data:
            raise ValueError("trailing data in PNG compressed image stream")
        decoded += decoder.flush()
    except zlib.error as exc:
        raise ValueError("invalid PNG compressed image data") from exc

    if len(decoded) != expected_decoded_bytes:
        raise ValueError("PNG decompressed data does not match declared dimensions")
    stride = row_bytes + 1
    if any(decoded[row * stride] > 4 for row in range(dimensions[1])):
        raise ValueError("invalid PNG scanline filter")

    return {"width": dimensions[0], "height": dimensions[1], "size_bytes": len(raw)}


def audit_manifest(manifest_path: Path, evidence_root: Path, allowed_origins: set[str]) -> dict[str, Any]:
    """Audit a JSON evidence manifest without network, browser, or write side effects."""
    # Check the caller-supplied paths before resolving: checking only the
    # resolved paths would hide that the original path itself was a symlink.
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("manifest must be a regular non-symlink file")
    if evidence_root.is_symlink() or not evidence_root.is_dir():
        raise ValueError("evidence root must be a regular directory")
    manifest_path = manifest_path.resolve(strict=True)
    evidence_root = evidence_root.resolve(strict=True)
    if not allowed_origins:
        raise ValueError("at least one explicit --allowed-origin is required")
    normalized_origins = {_origin(value) for value in allowed_origins}
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("unsupported manifest schema")
    if payload.get("provenance") != "OPERATOR_SUPPLIED_SCREENSHOTS_UNATTESTED":
        raise ValueError("manifest provenance must remain explicitly unattested")
    entries = payload.get("captures")
    if not isinstance(entries, list):
        raise ValueError("captures must be a list")

    by_cue: dict[str, dict[str, Any]] = {}
    duplicate_cues: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        cue_name = entry.get("cue")
        if not isinstance(cue_name, str):
            continue
        if cue_name in by_cue:
            duplicate_cues.add(cue_name)
        else:
            by_cue[cue_name] = entry

    results: list[dict[str, Any]] = []
    for cue in CUES:
        entry = by_cue.get(cue.cue)
        result: dict[str, Any] = {
            "cue": cue.cue, "service": cue.service, "view": cue.view,
            "required_state": cue.required_state, "status": "MISSING",
            "screenshot_sha256": None, "image": None,
            "runtime_authenticated": False, "business_validated": False,
            "human_approval_authenticated": False, "live_action_authorized": False,
            "provenance": "NO_CAPTURE_OR_VALIDATION",
        }
        if entry is None:
            results.append(result)
            continue
        if cue.cue in duplicate_cues:
            result.update(status="REJECTED_DUPLICATE_CUE", provenance="INVALID_MANIFEST")
            results.append(result)
            continue
        if entry.get("service") != cue.service or entry.get("view") != cue.view:
            result.update(status="REJECTED_CUE_MISMATCH", provenance="INVALID_MANIFEST")
            results.append(result)
            continue
        try:
            source_url = entry.get("source_url")
            if not isinstance(source_url, str) or _origin(source_url) not in normalized_origins:
                raise ValueError("source origin is not explicitly allowlisted")
            if not _utc_timestamp(entry.get("captured_at_utc")):
                raise ValueError("capture timestamp must include timezone")
            for field in ("run_id", "incident_id", "screenshot_sha256", "screenshot_path"):
                if not isinstance(entry.get(field), str) or not entry[field].strip():
                    raise ValueError(f"missing {field}")
            for field in ("run_id", "incident_id"):
                if len(entry[field]) > 128 or any(ord(ch) < 33 for ch in entry[field]):
                    raise ValueError(f"invalid {field}")
            digest = entry["screenshot_sha256"]
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError("invalid screenshot SHA-256")
            screenshot = _safe_file(evidence_root, entry["screenshot_path"])
            image_info = _verify_png(screenshot)
            observed = hashlib.sha256(screenshot.read_bytes()).hexdigest()
            if observed != digest:
                raise ValueError("screenshot SHA-256 mismatch")
            result.update(
                status="BYTES_VERIFIED_UNATTESTED",
                screenshot_sha256=observed,
                image=image_info,
                provenance="OPERATOR_SUPPLIED_SCREENSHOTS_UNATTESTED",
                source_origin=_origin(source_url),
                captured_at_utc=entry["captured_at_utc"],
                run_id=entry["run_id"],
                incident_id=entry["incident_id"],
                ticket_id=entry.get("ticket_id") if isinstance(entry.get("ticket_id"), str) else None,
            )
        except (OSError, ValueError, TypeError) as exc:
            result.update(status="REJECTED", provenance="INVALID_OR_UNVERIFIED_BYTES", reason=str(exc))
        results.append(result)

    accepted = sum(row["status"] == "BYTES_VERIFIED_UNATTESTED" for row in results)
    complete = accepted == len(CUES) and not duplicate_cues and len(entries) == len(CUES)
    return {
        "schema_version": 1,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "scope": "LOCAL_SCREENSHOT_BYTES_AND_OPERATOR_METADATA_ONLY",
        "source_execution_performed": False,
        "network_requests_performed": False,
        "application_identity_authenticated": False,
        "runtime_event_authenticated": False,
        "business_state_validated": False,
        "human_approval_authenticated": False,
        "live_action_authorized": False,
        "production_qualified": False,
        "capture_count": accepted,
        "expected_capture_count": len(CUES),
        "complete_byte_set": complete,
        "decision": "READY_FOR_SEPARATE_RUNTIME_REVIEW" if complete else "EVIDENCE_INCOMPLETE",
        "captures": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--allowed-origin", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = audit_manifest(args.manifest, args.evidence_root, set(args.allowed_origin))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    payload = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        if args.output.exists() or args.output.is_symlink():
            parser.error("refusing to overwrite existing output")
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["complete_byte_set"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
