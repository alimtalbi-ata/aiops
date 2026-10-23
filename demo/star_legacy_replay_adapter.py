"""Offline, deterministic, redacted bridge for the V2.13.4 Core replay contract.

Inputs are untrusted operator exports; neither this adapter nor a successful
replay attests runtime provenance, human approval, or remediation. No I/O.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import re
from collections.abc import Mapping

_RUN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{2,95}\Z")
_GROUPS = (("events", "run"), ("stages", "run"),
           ("analyses", "ledger"), ("critiques", "ledger"),
           ("policy_decisions", "ledger"))
_MAX_ROWS = 5000


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label}: object required")
    return value


def _rows(value, label):
    if not isinstance(value, list) or len(value) > _MAX_ROWS or any(not isinstance(x, dict) for x in value):
        raise ValueError(f"{label}: invalid collection")
    return value


def _time(value):
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            return None
        return stamp
    except (ValueError, OverflowError):
        return None


def _fingerprint(obj):
    try:
        canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("unserializable export") from exc
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_replay(run: Mapping, ledger: Mapping, evidence: Mapping) -> dict:
    """Produce a safe, deterministic *summary*, never raw export metadata."""
    run = _object(run, "run")
    ledger = _object(ledger, "ledger")
    evidence = _object(evidence, "evidence")
    meta = _object(run.get("run"), "run metadata")
    run_id = meta.get("run_id")
    if (not isinstance(run_id, str) or not _RUN.fullmatch(run_id)
            or ledger.get("run_id") != run_id or evidence.get("run_id") != run_id):
        raise ValueError("missing or contradictory run identity")
    if meta.get("mode") != "DEMO" or meta.get("status") not in ("BLOCKED", "RESOLVED"):
        raise ValueError("only explicitly DEMO BLOCKED/RESOLVED exports supported")
    items = _rows(evidence.get("items"), "evidence.items")
    ids = [item.get("evidence_id") for item in items]
    if any(not isinstance(i, str) or not _RUN.fullmatch(i) for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("missing, invalid or duplicate evidence ID")
    known = set(ids)
    frames = []
    for source, owner in _GROUPS:
        rows = _rows((run if owner == "run" else ledger).get(source), source)
        for position, row in enumerate(rows, 1):
            refs = row.get("evidence_ids", [])
            if (not isinstance(refs, list) or len(refs) > _MAX_ROWS
                    or any(not isinstance(x, str) or x not in known for x in refs)
                    or len(set(refs)) != len(refs)):
                raise ValueError(f"{source}: unknown/duplicate evidence reference")
            raw_stamp = next((row[k] for k in ("timestamp", "created_at", "occurred_at", "time")
                              if isinstance(row.get(k), str)), None)
            stamp = _time(raw_stamp)
            safe = {}
            if row.get("severity") in ("P1", "P2", "P3"):
                safe["severity"] = row["severity"]
            if isinstance(row.get("validated"), bool):
                safe["validated"] = row["validated"]
            confidence = row.get("confidence")
            if type(confidence) in (int, float) and math.isfinite(confidence) and 0 <= confidence <= 1:
                safe["confidence"] = confidence
            frames.append({"source": source, "source_index": position,
                           "evidence_ref_count": len(refs), "timestamp": stamp.isoformat() if stamp else None,
                           "metadata": safe})
    # Sort only when every frame has a timezone-aware timestamp. Python's sort
    # is stable for ties; otherwise preserve original export collection order.
    chronological = bool(frames) and all(f["timestamp"] is not None for f in frames)
    if chronological:
        frames.sort(key=lambda f: datetime.fromisoformat(f["timestamp"]))
    for index, frame in enumerate(frames, 1):
        frame["step"] = index
    return {
        "schema": "star-core-legacy-replay/v1", "run_id": run_id,
        "mode": "DEMO", "status": meta["status"],
        "chronology_proven_from_declared_timestamps": chronological,
        "frames": frames, "evidence_count": len(items),
        "input_content_sha256": {"run": _fingerprint(run), "ledger": _fingerprint(ledger),
                                 "evidence": _fingerprint(evidence)},
        "source_provenance": "OPERATOR_EXPORTS_NOT_INDEPENDENTLY_ATTESTED",
        "runtime_authenticated": False, "business_validated": False,
        "human_approval_authenticated": False, "live_remediation_authorized": False,
        "portal_integration_qualified": False,
    }
