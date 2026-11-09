"""Fail-closed adapter for Debian run_linkage_gate.py JSON reports.

A linkage report is a read-only observation, not an authenticated attestation.
This adapter never marks worker/HITL success from unrelated checks.
"""
import argparse
import json
from pathlib import Path
import sys

try:
    from .integration_evidence_gate import evaluate
except ImportError:
    from integration_evidence_gate import evaluate


def evaluate_linkage(report):
    if not isinstance(report, dict) or report.get("schema") != "aiops2-run-linkage-gate-v1" or report.get("read_only") is not True:
        return {"status": "HOLD", "reasons": ["INVALID_LINKAGE_REPORT"]}
    checks = report.get("checks")
    db = report.get("database")
    core = report.get("core")
    if not isinstance(checks, dict) or not isinstance(db, dict) or not isinstance(core, dict):
        return {"status": "HOLD", "reasons": ["INCOMPLETE_LINKAGE_REPORT"]}
    reasons = []
    if report.get("verdict") != "PASS":
        reasons.append("LINKAGE_VERDICT_NOT_PASS")
    for key in ("core_run", "core_api", "evidence_api", "critic_policy_outbox",
                "glpi_core_link", "itsm_readback", "temporal_worker_execution",
                "hitl_action_binding"):
        if checks.get(key) != "PASS":
            reasons.append("LINKAGE_" + key.upper() + "_NOT_PASS")
    links = db.get("glpi_links")
    xrefs = db.get("itsm_xref")
    if not isinstance(links, list) or not isinstance(xrefs, list):
        reasons.append("MISSING_GLPI_DB_ROWS")
    else:
        # Require the SAME ticket to have both confirmed Core linkage and verified readback.
        confirmed = {str(row["glpi_ticket_id"]) for row in links
                     if isinstance(row, dict) and row.get("state") == "CONFIRMED"
                     and type(row.get("glpi_ticket_id")) is int and row["glpi_ticket_id"] > 0}
        verified = {str(row["ticket_id"]) for row in xrefs
                    if isinstance(row, dict) and row.get("glpi_ticket_readback_verified") is True
                    and type(row.get("ticket_id")) is int and row["ticket_id"] > 0}
        if not confirmed.intersection(verified):
            reasons.append("GLPI_SAME_TICKET_READBACK_UNVERIFIED")
    run_id = report.get("run_id")
    if not isinstance(run_id, str) or not run_id.startswith("RUN-"):
        reasons.append("INVALID_RUN_ID")
    if reasons:
        return {"status": "HOLD", "reasons": reasons}
    # Even all PASS linkage checks cannot establish provenance independently.
    # The full gate needs authenticated independent source receipts.
    return {"status": "HOLD", "reasons": ["INDEPENDENT_SOURCE_ATTESTATIONS_REQUIRED"]}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("report", type=Path)
    args = p.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        result = evaluate_linkage(report)
    except (OSError, ValueError, UnicodeError):
        result = {"status": "HOLD", "reasons": ["INVALID_LINKAGE_JSON"]}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2

if __name__ == "__main__":
    sys.exit(main())
