"""Offline receipt validation; PASS validates claims, not their authenticity.

Required top-level fields are listed in _EXPECTED plus correlation_id. Status
values are exact, case-sensitive strings. Unknown fields confer no authority.
Run with: python3 ops/coordination/integration_evidence_gate.py receipt.json
"""

import argparse
import json
from pathlib import Path


_EXPECTED = (
    ("source_provenance", "REAL"),
    ("core_status", "SUCCESS"),
    ("worker_status", "SUCCESS"),
    ("policy_status", "APPROVED"),
    ("evidence_status", "VERIFIED"),
    ("glpi_core_link", "LINKED"),
    ("itsm_readback", "VERIFIED"),
)


def evaluate(receipt: dict) -> dict:
    """Return PASS with no reasons, or HOLD with deterministic reason codes.

    Each missing field yields MISSING_<FIELD>; present invalid values yield
    INVALID_<FIELD>. Non-object receipts yield INVALID_RECEIPT.
    """
    if not isinstance(receipt, dict):
        return {"status": "HOLD", "reasons": ["INVALID_RECEIPT"]}

    reasons = []
    for field, expected in _EXPECTED:
        if field not in receipt:
            reasons.append("MISSING_" + field.upper())
        elif not isinstance(receipt[field], str) or receipt[field] != expected:
            reasons.append("INVALID_" + field.upper())

    if "correlation_id" not in receipt:
        reasons.append("MISSING_CORRELATION_ID")
    elif (not isinstance(receipt["correlation_id"], str)
          or not receipt["correlation_id"].strip()):
        reasons.append("INVALID_CORRELATION_ID")
    return {"status": "HOLD" if reasons else "PASS", "reasons": reasons}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("nonstandard JSON constant")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path, help="JSON receipt file")
    args = parser.parse_args(argv)
    try:
        with args.receipt.open(encoding="utf-8") as stream:
            receipt = json.load(stream, object_pairs_hook=_unique_object,
                                parse_constant=_reject_constant)
        result = evaluate(receipt)
    except (OSError, ValueError, RecursionError):
        result = {"status": "HOLD", "reasons": ["INVALID_RECEIPT_FILE"]}
    print(json.dumps(result))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
