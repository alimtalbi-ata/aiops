"""Offline Golden Demo HITL story from the real sandbox approval library.

No Core/Temporal/GLPI interaction, no external command, no LIVE action.
Run with: python -m demo.hitl_golden_demo --output /tmp/hitl-story.json
"""
import argparse
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.shared.hitl_lab import approve, dry_run, initialize, propose, read_status


def build_story(now=None):
    clock = now if now is not None else datetime.now(timezone.utc)
    binding = {
        "incident_id": "INC-SIM-GOLDEN-PAYMENT",
        "run_id": "RUN-SIM-GOLDEN-PAYMENT",
        "recipe_id": "acme.demo.restart-service.v1",
        "target_id": "ACME-SIM-PAYMENTS-API",
        "params": {"service": "payments-api"},
        "mode": "DEMO",
    }
    with tempfile.TemporaryDirectory(prefix="aiops-hitl-sandbox-") as tmp:
        store = str(Path(tmp) / "hitl.sqlite")
        initialize(store)
        proposed = propose(store, proposer_id="demo-proposer", now=clock, **binding)
        awaiting = read_status(store, proposal_id=proposed["proposal_id"], now=clock)
        approved = approve(store, proposal_id=proposed["proposal_id"],
                           approver_id="demo-approver", approver_role="approver", now=clock)
        approved_state = read_status(store, proposal_id=proposed["proposal_id"], now=clock)
        receipt = dry_run(store, proposal_id=proposed["proposal_id"],
                          approval_token=approved["approval_token"], now=clock, **binding)
        planned = read_status(store, proposal_id=proposed["proposal_id"], now=clock)
    states = [awaiting, approved_state, planned]
    expected = ["AWAITING_HUMAN_APPROVAL", "APPROVED_FOR_DRY_RUN_ONLY", "DRY_RUN_PLANNED"]
    if [step["state"] for step in states] != expected or receipt["receipt_id"] != planned["receipt_id"]:
        raise RuntimeError("sandbox approval evidence inconsistent")
    if any(step["execution_allowed"] or step["effect_executed"] for step in states):
        raise RuntimeError("sandbox unexpectedly authorized an effect")
    story = {
        "schema": "aiops.hitl.sandbox-story.v1",
        "generated_at_utc": clock.astimezone(timezone.utc).isoformat(),
        "provenance": "LOCAL_SANDBOX_SQLITE_NOT_CORE",
        "simulation_only": True, "runtime_authenticated": False,
        "production_qualified": False, "live_remediation_authorized": False,
        "effect_executed": False,
        "steps": states,
    }
    canonical = json.dumps(story, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    story["story_sha256"] = hashlib.sha256(canonical).hexdigest()
    return story


def main():
    parser = argparse.ArgumentParser(description="Offline HITL sandbox story; no LIVE effects")
    parser.add_argument("--output", type=Path, help="Write untrusted synthetic story JSON")
    args = parser.parse_args()
    result = build_story()
    raw = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(raw, encoding="utf-8")
        print("SIMULATION_ONLY story written:", args.output)
    else:
        print(raw, end="")


if __name__ == "__main__":
    main()
