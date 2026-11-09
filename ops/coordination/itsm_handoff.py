"""Build a deterministic, fail-closed ITSM handoff from observed Core context.

This is an integration handoff contract, NOT a GLPI ticket creation or proof
of durable Core/GLPI reconciliation. No network calls or live writes.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def build_handoff(context):
    if not isinstance(context, dict) or context.get("schema") != "aiops2-core-case-context-v1":
        raise ValueError("invalid Core context schema")
    if context.get("read_only") is not True or context.get("source") != "core_http_get":
        raise ValueError("untrusted Core context source")
    checks = context.get("checks")
    if not isinstance(checks, dict) or checks.get("core_run") != "PASS" or checks.get("evidence_api") != "PASS":
        raise ValueError("Core and Evidence observations required")
    run_id, incident_id, run_status = (context.get(k) for k in ("run_id", "incident_id", "run_status"))
    if not isinstance(run_id, str) or not run_id.startswith("RUN-") or not isinstance(incident_id, str) or not incident_id:
        raise ValueError("missing correlation identifiers")
    if run_status not in ("CREATED", "WAITING", "RUNNING", "BLOCKED", "RESOLVED", "FAILED",
                           "CANCELLED", "SUCCESS", "PENDING"):
        raise ValueError("unsupported or missing run status")
    key = hashlib.sha256(("aiops2:itsm:v1:" + incident_id).encode("utf-8")).hexdigest()
    blocked = run_status == "BLOCKED"
    return {
        "schema": "aiops2-itsm-handoff-v1",
        "run_id": run_id,
        "incident_id": incident_id,
        "correlation_id": incident_id,
        "idempotency_key": "aiops2-itsm-" + key,
        "source": "core_case_context",
        "run_status": run_status,
        "policy_disposition": "DENIED" if blocked else "NOT_ESTABLISHED",
        "requested_operation": "UPSERT_INCIDENT_TRACKING",
        "execution_authorized": False,
        "execute_worker": False,
        "create_ticket_authorized": False,
        "existing_ticket_lookup_required": True,
        "glpi_ticket_id": None,
        "glpi_readback_verified": False,
        "core_link_persisted": False,
        "delivery_status": "NOT_SENT",
        "integration_status": "PENDING_ITSM_ADAPTER",
        "evidence_observed": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("context_json", type=Path, help="Core collector JSON")
    args = parser.parse_args(argv)
    try:
        result = build_handoff(json.loads(args.context_json.read_text(encoding="utf-8")))
    except (ValueError, OSError, UnicodeError) as exc:
        print(json.dumps({"status": "HOLD", "reason": type(exc).__name__}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
