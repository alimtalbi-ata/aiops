#!/usr/bin/env python3
"""Read-only AIOps2 evidence joiner: independent source receipts -> fail-closed gate.

This does not attest source authenticity. A caller must supply independently
collected, trusted runtime receipts; no status is inferred from filenames or
from synthetic fixtures. No GLPI/network calls or writes to production systems.
"""
import argparse
import json
from pathlib import Path
import sys

try:
    from .integration_evidence_gate import evaluate
except ImportError:
    from integration_evidence_gate import evaluate

SOURCES = {
    "core": ("core_status", "SUCCESS"),
    "worker": ("worker_status", "SUCCESS"),
    "policy": ("policy_status", "APPROVED"),
    "evidence": ("evidence_status", "VERIFIED"),
    "glpi": ("glpi_core_link", "LINKED"),
    "itsm": ("itsm_readback", "VERIFIED"),
}
MAX_BYTES = 1024 * 1024

def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON key")
        obj[key] = value
    return obj

def read_receipt(path):
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("missing or oversized receipt")
    return json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=unique_object,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))

def join(receipts, correlation_id):
    """Join six separately supplied source receipts without inventing success."""
    if not isinstance(correlation_id, str) or not correlation_id.strip():
        return {"status": "HOLD", "reasons": ["INVALID_CORRELATION_ID"]}
    assembled = {"correlation_id": correlation_id}
    reasons = []
    for source, (field, expected) in SOURCES.items():
        record = receipts.get(source)
        if not isinstance(record, dict):
            reasons.append("MISSING_SOURCE_" + source.upper())
            continue
        if record.get("correlation_id") != correlation_id:
            reasons.append("CORRELATION_MISMATCH_" + source.upper())
            continue
        if record.get("source_provenance") != "REAL":
            reasons.append("UNVERIFIED_PROVENANCE_" + source.upper())
            continue
        if not isinstance(record.get("evidence_ref"), str) or not record["evidence_ref"].strip():
            reasons.append("MISSING_EVIDENCE_REF_" + source.upper())
            continue
        # A claimed source status is never upgraded or normalized.
        assembled[field] = record.get("status")
    if reasons:
        return {"status": "HOLD", "reasons": reasons}
    assembled["source_provenance"] = "REAL"
    return evaluate(assembled)

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--correlation-id", required=True)
    for source in SOURCES:
        p.add_argument("--" + source, required=True, type=Path)
    args = p.parse_args(argv)
    receipts = {}
    errors = []
    for source in SOURCES:
        try:
            receipts[source] = read_receipt(getattr(args, source))
        except (OSError, ValueError, UnicodeError, RecursionError):
            errors.append("INVALID_SOURCE_FILE_" + source.upper())
    if errors:
        result = {"status": "HOLD", "reasons": errors}
    else:
        result = join(receipts, args.correlation_id)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2

if __name__ == "__main__":
    sys.exit(main())
