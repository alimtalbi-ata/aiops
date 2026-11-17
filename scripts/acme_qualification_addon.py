#!/usr/bin/env python3
"""ACME Workbench + Demo evidence aggregator (read-only, offline).

It does not launch Playwright or call the Portal, Core, Twin, GLPI or Docker.
Manifest declarations are untrusted: byte integrity is not runtime attestation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import struct
import zlib

SCENES = ("noc", "signals", "twin", "analyst_critic", "policy_hitl",
          "itsm_worker", "timeline")
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
PNG = b"\x89PNG\r\n\x1a\n"
MAX_JSON_BYTES = 65536
MAX_PNG_BYTES = 10 * 1024 * 1024



def png_structure_valid(raw: bytes) -> bool:
    """Check complete PNG framing, CRCs, IHDR, IDAT and terminal IEND.

    This is a structural integrity check, NOT a pixel decoder or browser proof.
    """
    if not raw.startswith(PNG) or len(raw) < 8 + 12 + 13 + 12:
        return False
    offset = 8
    seen_ihdr = seen_idat = seen_iend = False
    while offset + 12 <= len(raw):
        length = struct.unpack(">I", raw[offset:offset + 4])[0]
        kind = raw[offset + 4:offset + 8]
        end = offset + 12 + length
        if length > MAX_PNG_BYTES or end > len(raw):
            return False
        payload = raw[offset + 8:offset + 8 + length]
        crc = struct.unpack(">I", raw[offset + 8 + length:end])[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != crc:
            return False
        if not seen_ihdr:
            if kind != b"IHDR" or length != 13:
                return False
            width, height = struct.unpack(">II", payload[:8])
            if not (1 <= width <= 8192 and 1 <= height <= 8192):
                return False
            seen_ihdr = True
        elif kind == b"IHDR":
            return False
        if kind == b"IDAT":
            seen_idat = True
        if kind == b"IEND":
            if length != 0 or not seen_idat or end != len(raw):
                return False
            seen_iend = True
            break
        offset = end
    return seen_ihdr and seen_idat and seen_iend


def read_json(path: Path):
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("JSON input exceeds size limit")
    return json.loads(path.read_text(encoding="utf-8"))


def inspect_host_receipt(value, expected_sha: str):
    """Evaluate existing Debian runner's *declarations*, not a host attestation."""
    problems = []
    if not isinstance(value, dict):
        return ["HOST_RECEIPT_INVALID"]
    if value.get("schema") != "aiops.portal-host-playwright-snapshots.v1":
        problems.append("HOST_SCHEMA_INVALID")
    if value.get("status") != "PASS_ANONYMOUS_SYNTHETIC_BROWSER_ONLY":
        problems.append("HOST_STATUS_NOT_PASS")
    if value.get("stable_checkout_sha") != expected_sha:
        problems.append("HOST_SHA_MISMATCH")
    if not isinstance(value.get("portal_image_id"), str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", value["portal_image_id"]):
        problems.append("HOST_IMAGE_UNKNOWN")
    if value.get("live_effects") != 0 or type(value.get("live_effects")) is not int:
        problems.append("HOST_LIVE_EFFECTS_INVALID")
    for key in ("page_errors_count", "unexpected_console_errors_count",
                "failed_requests_count", "blocked_requests_count"):
        if type(value.get(key)) is not int or value[key] != 0:
            problems.append("HOST_" + key.upper() + "_INVALID")
    shots = value.get("screenshots")
    if not isinstance(shots, list) or len(shots) < 1:
        problems.append("HOST_SCREENSHOTS_MISSING")
    return problems


def inspect_scenes(manifest, root: Path, expected_sha: str):
    """Seven unique scene PNGs with actual byte hashes; no fabricated PASS."""
    errors = []
    if not isinstance(manifest, dict):
        return ["SCENES_MANIFEST_INVALID"]
    if manifest.get("schema") != "aiops.acme-scene-evidence.v1":
        errors.append("SCENES_SCHEMA_INVALID")
    if manifest.get("source_sha") != expected_sha:
        errors.append("SCENES_SHA_MISMATCH")
    if manifest.get("scenario_id") != "ACME-SAN-PAYMENTS" or manifest.get("tenant_id") != "ACME-TEST":
        errors.append("SCENES_SCOPE_INVALID")
    if manifest.get("mode") != "SIMULATION" or manifest.get("live") != "NO_GO":
        errors.append("SCENES_LIVE_FENCE_INVALID")
    scenes = manifest.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != len(SCENES):
        return errors + ["SCENES_COUNT_INVALID"]
    root = root.resolve(strict=True)
    seen = set()
    filenames = set()
    for item in scenes:
        if not isinstance(item, dict):
            errors.append("SCENE_INVALID")
            continue
        sid = item.get("id")
        if sid not in SCENES or sid in seen:
            errors.append("SCENE_ID_INVALID")
        else:
            seen.add(sid)
        if item.get("status") != "PASS":
            errors.append("SCENE_NOT_PASS")
        name = item.get("file")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9_-]{3,64}\.png", name) or name in filenames:
            errors.append("SCENE_FILE_INVALID")
            continue
        filenames.add(name)
        path = root / name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            errors.append("SCENE_FILE_MISSING_OR_UNSAFE")
            continue
        if path.stat().st_size > MAX_PNG_BYTES:
            errors.append("SCENE_PNG_TOO_LARGE")
            continue
        raw = path.read_bytes()
        if not png_structure_valid(raw):
            errors.append("SCENE_PNG_HEADER_INVALID")
        if not isinstance(item.get("sha256"), str) or not DIGEST.fullmatch(item["sha256"]) or hashlib.sha256(raw).hexdigest() != item["sha256"]:
            errors.append("SCENE_HASH_MISMATCH")
        if type(item.get("simulation_visible")) is not bool or not item["simulation_visible"]:
            errors.append("SCENE_SIMULATION_NOT_VERIFIED")
        if type(item.get("external_requests")) is not int or item["external_requests"] != 0:
            errors.append("SCENE_NETWORK_NOT_VERIFIED")
    if seen != set(SCENES):
        errors.append("SCENE_COVERAGE_INCOMPLETE")
    return sorted(set(errors))


def qualify(receipt, host_receipt=None, scene_manifest=None, scene_root=None,
            expected_sha=None, now=None):
    """Three independent evidence axes; never upgrade metadata to runtime proof."""
    try:
        from scripts.acme_demo_readiness import assess
    except ModuleNotFoundError:
        from acme_demo_readiness import assess
    readiness = assess(receipt, now=now)
    sha_ok = isinstance(expected_sha, str) and SHA.fullmatch(expected_sha) is not None
    host_errors = ["HOST_NOT_PROVIDED"]
    scene_errors = ["SCENES_NOT_PROVIDED"]
    if host_receipt is not None:
        host_errors = inspect_host_receipt(host_receipt, expected_sha) if sha_ok else ["EXPECTED_SHA_INVALID"]
    if scene_manifest is not None:
        if not sha_ok:
            scene_errors = ["EXPECTED_SHA_INVALID"]
        elif scene_root is None:
            scene_errors = ["SCENES_ROOT_MISSING"]
        else:
            try:
                scene_errors = inspect_scenes(scene_manifest, Path(scene_root), expected_sha)
            except (OSError, ValueError):
                scene_errors = ["SCENES_UNREADABLE"]
    offline_pass = readiness["verdict"] == "GO_SIMULATION_ONLY"
    # Even if all metadata and bytes check out, execution identity, browser
    # authenticity, 17-stage cross-service joins and tenant ACL remain unproven.
    return {
        "schema": "aiops.acme-qualification-addon.v1",
        "scenario_id": "ACME-SAN-PAYMENTS",
        "tenant_id": "ACME-TEST",
        "mode": "SIMULATION",
        "offline_receipt": readiness,
        "host_receipt_metadata": {"status": "METADATA_CONSISTENT" if not host_errors else "NOT_QUALIFIED",
                                  "reasons": host_errors},
        "seven_scene_png_integrity": {"status": "BYTES_CONSISTENT" if not scene_errors else "NOT_QUALIFIED",
                                      "reasons": scene_errors},
        "runtime_e2e": "NOT_VERIFIED",
        "core_twin_join": "NOT_VERIFIED",
        "tenant_acl": "NOT_VERIFIED",
        "deployed_sha_attestation": "NOT_VERIFIED",
        "verdict": "OFFLINE_SIMULATION_GATE_PASS_ONLY" if offline_pass else "NO_GO",
        "live": "NO_GO",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--host-receipt", type=Path)
    parser.add_argument("--scenes-manifest", type=Path)
    parser.add_argument("--scenes-dir", type=Path)
    parser.add_argument("--expected-sha")
    args = parser.parse_args(argv)
    try:
        receipt = read_json(args.receipt)
        host = read_json(args.host_receipt) if args.host_receipt else None
        scenes = read_json(args.scenes_manifest) if args.scenes_manifest else None
        result = qualify(receipt, host, scenes, args.scenes_dir, args.expected_sha)
    except (OSError, UnicodeError, ValueError, TypeError):
        result = {"schema": "aiops.acme-qualification-addon.v1",
                  "verdict": "NO_GO", "reasons": ["INPUT_UNREADABLE"], "live": "NO_GO"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["verdict"] == "OFFLINE_SIMULATION_GATE_PASS_ONLY" else 2


if __name__ == "__main__":
    sys.exit(main())
