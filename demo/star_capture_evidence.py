"""Offline, fail-closed evidence ingestion for STAR demo screenshots.

No browser automation, HTTP, Docker, credential access, or application mutation.
The operator captures PNGs separately; this module verifies bytes, identity and
chronology before producing a manifest explicitly NOT claiming runtime approval.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Mapping

from demo.star_snapshot_choreography import CUE_BY_NAME, validate_capture
from demo.star_png_integrity import inspect_png

HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,95}$")

def _contained_file(evidence_root: Path, relative_path: str) -> Path:
    # Evidence path format validated separately; resolve again against symlinks.
    if not relative_path.startswith("evidence/"):
        raise ValueError("evidence path required")
    base = evidence_root.resolve(strict=True)
    target = (base / relative_path).resolve(strict=True)
    if not target.is_relative_to(base) or not target.is_file():
        raise ValueError("capture escaped evidence root or not a file")
    return target

def verify_manifest(
    evidence_root: Path,
    run_id: str,
    capture_records: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Check screenshots against their timeline cues and a single run identity.

    A successful check is an *integrity check*, not authentication that an
    external application was genuinely observed or an action authorized.
    """
    if not isinstance(run_id, str) or not SAFE_ID.fullmatch(run_id):
        raise ValueError("invalid canonical run ID")
    unknown = set(capture_records) - set(CUE_BY_NAME)
    if unknown:
        raise ValueError("unrecognized STAR cue")
    entries = []
    previous = None
    seen_digests: set[str] = set()
    for cue_name, cue in CUE_BY_NAME.items():
        record = capture_records.get(cue_name)
        if record is None:
            entries.append({"cue": cue_name, "status": "missing"})
            continue
        if record.get("run_id") != run_id:
            raise ValueError("cross-run capture blocked")
        meta = validate_capture(cue_name, record)
        if not meta["metadata_complete"]:
            entries.append({"cue": cue_name, "status": meta["proof_state"]})
            continue
        path = _contained_file(evidence_root, str(record["screenshot_path"]))
        actual_digest, size = inspect_png(path)
        declared_digest = record["sha256"]
        if not isinstance(declared_digest, str) or not HEX64.fullmatch(declared_digest):
            raise ValueError("invalid expected SHA")
        if actual_digest != declared_digest:
            raise ValueError("screenshot hash mismatch")
        # Two distinct STAR scenes cannot be substantiated by identical PNG
        # bytes, even if both records carry a valid SHA-256. This catches
        # accidental replay/relabeling of the same image across applications.
        if actual_digest in seen_digests:
            raise ValueError("screenshot reused across STAR cues")
        seen_digests.add(actual_digest)
        captured = datetime.fromisoformat(str(record["captured_at"]).replace("Z", "+00:00"))
        if previous is not None and captured < previous:
            raise ValueError("nonmonotonic capture timeline")
        previous = captured
        entries.append({
            "cue": cue_name, "status": "integrity_checked",
            "sha256": actual_digest, "bytes": size,
            "captured_at": captured.isoformat(),
            "view": cue.view,
        })
    return {
        "schema": "star-capture-evidence-v1",
        "run_id": run_id,
        "entries": entries,
        "integrity_checked": all(e["status"] == "integrity_checked" for e in entries),
        "runtime_authenticated": False,
        "business_validated": False,
        "human_approval_authenticated": False,
        "live_action_authorized": False,
    }

def verify_file(manifest_path: Path, root: Path) -> dict[str, object]:
    """Read untrusted manifest locally and return only a sanitized summary."""
    if manifest_path.stat().st_size > 300_000:
        raise ValueError("manifest too large")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("captures"), dict):
        raise ValueError("invalid manifest schema")
    return verify_manifest(root, data.get("run_id"), data["captures"])

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify_file(args.manifest, args.root), indent=2, ensure_ascii=False))
