#!/usr/bin/env python3
"""Fail-closed functional acceptance for the FS147 synthetic filesystem use case.

Consumes a reviewed, sanitized E2E receipt. Never triggers actions, HITL or GLPI.
A green generic CI check or Docker health status is not an E2E receipt.
"""
import argparse
import json
from pathlib import Path

STAGES = ("filesystem_incident", "twin_evidence", "core_run",
          "worker_analysis", "worker_critique", "policy_decision",
          "glpi_ticket_147", "hitl_action_binding", "safe_resume")
REQUIRED = ("run_id", "source", "result")


def evaluate(receipt):
    if receipt.get("schema") != "aiops2-fs147-functional-e2e-v1":
        raise ValueError("unsupported receipt schema")
    if receipt.get("mode") != "SIMULATED":
        raise ValueError("receipt must explicitly be SIMULATED")
    stages = receipt.get("stages")
    if not isinstance(stages, dict):
        raise ValueError("stages must be a mapping")
    failures = []
    run_id = receipt.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        failures.append("missing_run_id")
    if receipt.get("real_effects_executed") is not False:
        failures.append("real_effects_must_be_false")
    for name in STAGES:
        stage = stages.get(name)
        if not isinstance(stage, dict):
            failures.append(name + ":missing")
            continue
        for field in REQUIRED:
            if not isinstance(stage.get(field), str) or not stage[field].strip():
                failures.append(name + ":missing_" + field)
        if stage.get("result") != "PASS":
            failures.append(name + ":not_pass")
        if stage.get("run_id") != run_id:
            failures.append(name + ":run_id_mismatch")
        if not isinstance(stage.get("evidence_ref"), str) or not stage["evidence_ref"].strip():
            failures.append(name + ":missing_evidence_ref")
    return {
        "schema": "aiops2-fs147-functional-e2e-verdict-v1",
        "run_id": run_id,
        "result": "PASS" if not failures else "BLOCKED",
        "failures": failures,
        "release_decision": "HOLD",
        "note": "Receipt consistency only; independent verification of source artifacts and host provenance is required.",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("receipt", type=Path)
    args = p.parse_args()
    verdict = evaluate(json.loads(args.receipt.read_text(encoding="utf-8")))
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0 if verdict["result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
