#!/usr/bin/env python3
"""Run the ACME incident -> hypothetical remediation -> evidence gate offline.

No GLPI, Grafana, n8n, Temporal, database or network connection is made.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from portal.acme_demo_simulation_pipeline import run_acme_demo_simulation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline ACME DEMO simulation (no side effects)")
    parser.add_argument("--tenant", default="acme-demo",
                        help="DEMO tenant identifier; no production tenant ACL is implied")
    parser.add_argument("--verify", action="store_true",
                        help="Recompute the simulation receipt before emitting output")
    args = parser.parse_args(argv)
    try:
        result = run_acme_demo_simulation(tenant_id=args.tenant)
        if args.verify:
            from portal.acme_isolated_remediation_simulator import verify_simulation_receipt
            receipt = result["simulation"]["receipt"]
            request = {
                "schema": "aiops.demo-remediation-simulation-request.v1",
                "mode": "DEMO",
                "tenant_id": receipt["tenant_id"],
                "incident_id": receipt["incident_id"],
                "action_id": receipt["action_id"],
                "action_kind": receipt["action_kind"],
                "policy_decision": "SIMULATE_ONLY",
                "before": receipt["before"],
            }
            if not verify_simulation_receipt(request, result["simulation"]):
                raise ValueError("simulation_receipt_verification_failed")
        if (result["actual_recovery_state"] != "UNKNOWN"
                or result["live_remediation_authorized"] is not False):
            raise ValueError("demo_safety_gate_failed")
    except (ValueError, TypeError, KeyError) as exc:
        print(f"ACME DEMO refused: {type(exc).__name__}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
