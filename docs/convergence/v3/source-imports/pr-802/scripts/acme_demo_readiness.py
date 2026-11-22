#!/usr/bin/env python3
"""Offline, read-only readiness verdict for the ACME golden demo.

Consumes a Debian E2E receipt, never invokes Docker, HTTP or external APIs.
A simulation PASS is not a LIVE authorization.
"""
import argparse
import datetime as dt
import json
import re
from pathlib import Path
import sys

SCHEMA = "aiops.debian-acme-sim-e2e.v1"
REQUIRED_STAGES = (
    "capability_simulator", "capability_core", "capability_twin",
    "capability_policy", "capability_worker", "simulator_start",
    "pre_resolution_core", "pre_resolution_twin", "pre_resolution_policy",
    "pre_resolution_worker", "worker_no_effect", "core_finalization",
    "post_resolution_core", "post_resolution_twin",
    "post_resolution_policy", "post_resolution_worker", "resolved",
)
REQUIRED_IDS = ("incident_id", "run_id", "ticket_id", "proposal_id", "approval_id")

def assess(value, now=None, max_age_minutes=60):
    reasons = []
    if not isinstance(value, dict):
        return {"verdict": "NO_GO", "reasons": ["INVALID_RECEIPT"]}
    for key, expected in (("schema", SCHEMA), ("tenant_id", "ACME-TEST"),
                          ("scenario_id", "ACME-SAN-PAYMENTS"),
                          ("mode", "SIMULATION"), ("status", "PASS"),
                          ("reason", "SIMULATED_SANDBOX_ONLY"),
                          ("approval_issuer", "TWIN_ACME_SIMULATED"),
                          ("human_approval_claimed", False),
                          ("live_effects_allowed", False),
                          ("real_glpi_writes_allowed", False),
                          ("docker_mutations", 0)):
        if type(value.get(key)) is not type(expected) or value.get(key) != expected:
            reasons.append("INVALID_" + key.upper())
    try:
        stamp = dt.datetime.fromisoformat(value["collected_at"].replace("Z", "+00:00"))
        current = now or dt.datetime.now(dt.timezone.utc)
        if stamp.tzinfo is None or not dt.timedelta(0) <= current - stamp <= dt.timedelta(minutes=max_age_minutes):
            reasons.append("STALE_OR_FUTURE_RECEIPT")
    except (KeyError, TypeError, ValueError):
        reasons.append("INVALID_TIMESTAMP")
    attempt_id = value.get("attempt_id")
    if type(attempt_id) is not str or not re.fullmatch(r"ACME-SIM-[A-F0-9]{16}", attempt_id):
        reasons.append("INVALID_ATTEMPT_ID")
    stages = value.get("stages")
    if not isinstance(stages, dict) or any(stages.get(k) != "PASS" for k in REQUIRED_STAGES):
        reasons.append("INCOMPLETE_E2E_STAGES")
    ids = value.get("ids")
    if not isinstance(ids, dict) or any(not isinstance(ids.get(k), str) or not ids[k].strip() for k in REQUIRED_IDS):
        reasons.append("MISSING_CORRELATED_IDS")
    if isinstance(ids, dict):
        if not str(ids.get("ticket_id", "")).startswith("SIM-GLPI-"):
            reasons.append("INVALID_SIMULATED_TICKET_ID")
        if not str(ids.get("approval_id", "")).startswith("SIM-APP-"):
            reasons.append("INVALID_SIMULATED_APPROVAL_ID")
    return {"verdict": "GO_SIMULATION_ONLY" if not reasons else "NO_GO",
            "reasons": reasons, "live": "NO_GO"}

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("receipt", type=Path)
    p.add_argument("--max-age-minutes", type=int, default=60)
    args = p.parse_args(argv)
    if args.max_age_minutes <= 0 or args.max_age_minutes > 1440:
        p.error("max age must be 1..1440 minutes")
    try:
        if args.receipt.stat().st_size > 65536:
            raise ValueError("oversize receipt")
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        result = assess(receipt, max_age_minutes=args.max_age_minutes)
    except (OSError, UnicodeError, ValueError) as exc:
        result = {"verdict": "NO_GO", "reasons": ["UNREADABLE_RECEIPT"], "live": "NO_GO"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["verdict"] == "GO_SIMULATION_ONLY" else 2

if __name__ == "__main__":
    sys.exit(main())
