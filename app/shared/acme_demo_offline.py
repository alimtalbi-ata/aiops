"""Offline ACME remediation demonstration fixture; never contacts a service.

Usage: python3 -m app.shared.acme_demo_offline --outcome SUCCESS
       python3 -m app.shared.acme_demo_offline --outcome FAILURE
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone

from .remediation_lab import validate_proposal
from .acme_remediation_receipt import build_run_remediation_receipt


def demo_receipt(outcome: str = "SUCCESS") -> dict:
    """Produce a deterministic, explicitly unverified SAN-adjacent Linux demo.

    This fixture demonstrates the *contract*, not a real SAN failover or recovery.
    """
    run = {
        "run_id": "RUN-ACME-OFFLINE-001",
        "scenario_id": "SCN-ACME-LINUX-RECOVERY-WHATIF",
        "mode": "DEMO",
        "synthetic": True,
    }
    proposal = {
        "proposal_id": "P-ACME-OFFLINE-001",
        "recipe_id": "ansible-service-restart",
        "recipe_version": "1.0.0",
        "target_ci": "ACME-LNX-01",
        "parameters": {"service": "erp", "credential_ref": "vault://acme/demo"},
        "mode": "DEMO",
        "requested_by": "analyst-fixture",
    }
    _, digest = validate_proposal(proposal)
    decision = {
        "state": "APPROVED",
        "proposal_digest": digest,
        "actor_id": "approver-fixture",
        "actor_role": "approver",
        "authenticated": True,
        "expires_at": "2026-10-30T00:00:00Z",
        "requested_by": "analyst-fixture",
    }
    preconditions = {
        "ci_fresh": True,
        "owner_fenced": True,
        "service_exists": True,
        "maintenance_window": True,
    }
    before = {"target_ci": "ACME-LNX-01", "health": "DEGRADED", "service_available": False}
    return build_run_remediation_receipt(
        run, proposal, decision, preconditions, before,
        ["EVD-ACME-OFFLINE-001", "EVD-ACME-OFFLINE-002"],
        outcome=outcome,
        now=datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic no-effect ACME what-if demonstration")
    parser.add_argument("--outcome", choices=("SUCCESS", "FAILURE"), default="SUCCESS")
    args = parser.parse_args()
    print(json.dumps(demo_receipt(args.outcome), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
