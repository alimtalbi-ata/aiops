#!/usr/bin/env python3
"""FS147 read-only integration receipt gate. No network calls or mutations.

Usage:
  python scripts/fs/fs147_receipt_gate.py --self-test
  python scripts/fs/fs147_receipt_gate.py /path/to/operator-collected-receipt.json

Receipt is an *evidence index*, not proof by itself: every proof URL must point
to a real, independently reviewable artifact. No fake HITL/RESOLVED.
"""
import argparse
import json
import sys

STAGES = ("prometheus", "core_run", "core_evidence", "worker_analyst",
          "worker_critic", "policy", "glpi_147", "hitl_native", "safe_resume")
REQUIRED = ("alert_fingerprint", "incident_id", "run_id", "evidence_id",
            "glpi_ticket_id", "scenario", "mode", "stages")


def validate(r):
    errors = []
    if not isinstance(r, dict):
        return ["receipt must be an object"]
    for key in REQUIRED:
        if key not in r:
            errors.append("missing " + key)
    if errors:
        return errors
    if r["glpi_ticket_id"] != 147:
        errors.append("ticket must be integer 147")
    if r["scenario"] != "AIOPS2-REAL-FS-20261106":
        errors.append("scenario mismatch")
    if r["mode"] != "DEMO":
        errors.append("only DEMO lab evidence allowed")
    for key in ("alert_fingerprint", "incident_id", "run_id", "evidence_id"):
        if not isinstance(r[key], str) or not r[key].strip():
            errors.append("invalid " + key)
    stages = r["stages"]
    if not isinstance(stages, dict):
        return errors + ["stages must be an object"]
    for stage in STAGES:
        entry = stages.get(stage)
        if not isinstance(entry, dict):
            errors.append("missing stage " + stage)
            continue
        if entry.get("status") != "VERIFIED":
            errors.append("unverified stage " + stage)
        if not isinstance(entry.get("proof_url"), str) or not entry["proof_url"].startswith(("https://", "http://")):
            errors.append("missing proof URL " + stage)
        if entry.get("run_id") != r["run_id"]:
            errors.append("run mismatch " + stage)
    hitl = stages.get("hitl_native", {})
    if isinstance(hitl, dict):
        for key in ("ticket_id", "run_id", "alert_fingerprint", "action", "path", "expires_at", "validator_id", "approval_id"):
            if not hitl.get(key):
                errors.append("HITL missing " + key)
        if hitl.get("ticket_id") != 147:
            errors.append("HITL ticket mismatch")
        if hitl.get("run_id") != r["run_id"]:
            errors.append("HITL run mismatch")
        if hitl.get("alert_fingerprint") != r["alert_fingerprint"]:
            errors.append("HITL alert fingerprint mismatch")
    if r.get("production_deployment") is True:
        errors.append("production deployment cannot be certified by lab gate")
    if r.get("result") == "RESOLVED" and not r.get("post_action_measurement_proof_url"):
        errors.append("RESOLVED without post-action proof")
    return errors


def self_test():
    # Negative-only self tests: never manufacture a positive HITL receipt.
    assert "missing alert_fingerprint" in validate({})
    assert "ticket must be integer 147" in validate({
        **{k: "x" for k in REQUIRED}, "glpi_ticket_id": 146,
        "scenario": "AIOPS2-REAL-FS-20261106", "mode": "DEMO", "stages": {}
    })
    assert "stages must be an object" in validate({
        **{k: "x" for k in REQUIRED}, "glpi_ticket_id": 147,
        "scenario": "AIOPS2-REAL-FS-20261106", "mode": "DEMO", "stages": []
    })
    print("SELF_TEST_PASS: negative contract cases only")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("receipt", nargs="?")
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.receipt:
        p.error("receipt path required (no implicit success)")
    with open(args.receipt, encoding="utf-8") as f:
        receipt = json.load(f)
    errors = validate(receipt)
    if errors:
        for error in errors:
            print("NO_GO:", error, file=sys.stderr)
        return 1
    print("RECEIPT_SCHEMA_PASS (proof URLs still require independent review; NOT deployment approval)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
