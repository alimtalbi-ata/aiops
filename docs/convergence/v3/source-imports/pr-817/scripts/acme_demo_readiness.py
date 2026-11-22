#!/usr/bin/env python3
"""Offline, read-only readiness verdict for the ACME synthetic demo.

Requires Pydantic v2. No Docker, HTTP or external API calls.
A simulation PASS is never a LIVE authorization.
"""
import argparse
import json
from pathlib import Path
import sys

from pydantic import ValidationError

try:
    from scripts.acme_receipt_model import AcmeReceipt, REQUIRED_STAGES, SCHEMA
except ModuleNotFoundError:
    from acme_receipt_model import AcmeReceipt, REQUIRED_STAGES, SCHEMA

REQUIRED_IDS = ("incident_id", "run_id", "ticket_id", "proposal_id", "approval_id")

def assess(value, now=None, max_age_minutes=60):
    if not isinstance(value, dict):
        return {"verdict": "NO_GO", "reasons": ["INVALID_RECEIPT"], "live": "NO_GO"}
    try:
        # JSON mode parses ISO-8601 timestamps while strict model validation
        # rejects coercions such as boolean false for docker_mutations=0.
        AcmeReceipt.model_validate_json(
            json.dumps(value),
            context={"now": now, "max_age_minutes": max_age_minutes},
        )
    except (ValidationError, TypeError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            reasons = {"INVALID_" + "_".join(str(part).upper() for part in error["loc"])
                       if error["loc"] else "VALIDATION_ERROR"
                       for error in exc.errors()}
        else:
            reasons = {"INVALID_RECEIPT"}
        return {"verdict": "NO_GO", "reasons": sorted(reasons) or ["VALIDATION_ERROR"],
                "live": "NO_GO"}
    return {"verdict": "GO_SIMULATION_ONLY", "reasons": [], "live": "NO_GO"}

def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _reject_json_constant(value):
    raise ValueError("INVALID_JSON_CONSTANT")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("receipt", type=Path)
    p.add_argument("--max-age-minutes", type=int, default=60)
    args = p.parse_args(argv)
    if not 1 <= args.max_age_minutes <= 1440:
        p.error("max age must be 1..1440 minutes")
    try:
        if args.receipt.stat().st_size > 65536:
            raise ValueError("oversize receipt")
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"),
                             object_pairs_hook=_unique_object,
                             parse_constant=_reject_json_constant)
        result = assess(receipt, max_age_minutes=args.max_age_minutes)
    except (OSError, UnicodeError, ValueError):
        result = {"verdict": "NO_GO", "reasons": ["UNREADABLE_RECEIPT"], "live": "NO_GO"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["verdict"] == "GO_SIMULATION_ONLY" else 2

if __name__ == "__main__":
    sys.exit(main())
