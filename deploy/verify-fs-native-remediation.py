#!/usr/bin/env python3
"""Read-only validation of the native #423 synthetic remediation receipt.

This is NOT host provenance, source attestation, or E2E verification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path("/home/aiops/.local/state/aiops2-demo-filesystem")
RUN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
PHASES = {"OPEN", "ACTION_APPLIED", "FINALIZED_SIMULATED"}

def verify(run_id, root=ROOT):
    if not RUN.fullmatch(run_id):
        raise ValueError("invalid run-id")
    root = Path(root)
    path = root / "remediation" / run_id
    for part in (root, root / "remediation", path, path / "state.json", path / "receipt.json"):
        if part.is_symlink():
            raise ValueError("symlink forbidden")
    if not path.is_dir():
        raise ValueError("missing run directory")
    raw = (path / "state.json").read_bytes()
    state = json.loads(raw)
    receipt = json.loads((path / "receipt.json").read_bytes())
    if state.get("run_id") != run_id or receipt.get("run_id") != run_id:
        raise ValueError("run-id mismatch")
    if receipt.get("state_sha256") != hashlib.sha256(raw).hexdigest():
        raise ValueError("state digest mismatch")
    if receipt.get("synthetic_only") is not True or receipt.get("live_effects") is not False:
        raise ValueError("unsafe receipt")
    for field in ("incident", "proposed", "action", "phase", "used_mib", "capacity_mib"):
        if receipt.get(field) != state.get(field):
            raise ValueError("state/receipt mismatch: " + field)
    if state.get("phase") not in PHASES:
        raise ValueError("unknown phase")
    if state.get("incident") not in ("OPEN_SIMULATED", "MITIGATED_SIMULATED"):
        raise ValueError("unknown incident")
    if type(state.get("used_mib")) is not int or type(state.get("capacity_mib")) is not int:
        raise ValueError("invalid capacity")
    if not 0 <= state["used_mib"] <= state["capacity_mib"]:
        raise ValueError("invalid usage")
    return {"status": "NATIVE_SYNTHETIC_RECEIPT_VALID_ONLY",
            "run_id": run_id, "state_sha256": receipt["state_sha256"],
            "host_provenance": "NOT_ATTESTED", "source_sha": "NOT_ATTESTED"}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    args = p.parse_args()
    try:
        print(json.dumps(verify(args.run_id), sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "NO_GO", "reason": str(exc)}), file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
