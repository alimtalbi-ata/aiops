#!/usr/bin/env python3
"""AIOps2 use-case acceptance: distinguish safe policy block from broken linkage.

Consumes existing read-only per-run gate output; never triggers an action or
creates an ITSM ticket. Exit 0 only when all requested assertions are proved.
"""
import argparse
import json
from pathlib import Path

def assess(report, expect="blocked"):
    checks=report.get("checks") or {}
    core=report.get("core") or {}
    database=report.get("database") or {}
    run=database.get("run") or {}
    actual_status=str(run.get("status") or core.get("run",{}).get("status") or "").upper()
    outbox=database.get("critic_outbox") or []
    safe_block=(
        actual_status=="BLOCKED"
        and checks.get("core_run")=="PASS"
        and checks.get("core_api")=="PASS"
        and checks.get("critic_policy_outbox")=="PASS"
        and any(x.get("status")=="RECONCILED" and x.get("policy_decision_id") for x in outbox)
    )
    observed=report.get("external_glpi_observation") or {}
    ticket_id=observed.get("ticket_id")
    links=database.get("glpi_links") or []
    linked_ids={str(x.get("glpi_ticket_id")) for x in links if x.get("glpi_ticket_id") is not None}
    xref_verified=bool(ticket_id is not None and str(ticket_id) in linked_ids
                       and checks.get("itsm_readback")=="PASS")
    assertions={
        "run_and_core_consistent": checks.get("core_run")=="PASS" and checks.get("core_api")=="PASS",
        "evidence_available": checks.get("evidence_api")=="PASS",
        "safe_policy_block": safe_block if expect=="blocked" else None,
        "itsm_link_verified": xref_verified,
        "temporal_worker_verified": checks.get("temporal_worker_execution")=="PASS",
        "hitl_binding_verified": checks.get("hitl_action_binding")=="PASS",
    }
    missing=[k for k,v in assertions.items() if v is not True]
    return {
        "schema":"aiops2-usecase-acceptance-v1",
        "run_id":report.get("run_id"),
        "expected_outcome":expect,
        "observed_run_status":actual_status or "UNKNOWN",
        "safe_block_confirmed":safe_block,
        "assertions":assertions,
        "unverified":missing,
        "verdict":"PASS" if not missing else "HOLD",
        "interpretation":("Policy BLOCKED is a valid safety outcome, not an execution failure; "
                          "it does not prove Temporal, HITL or ITSM linkage."),
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--linkage-report",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--expect",choices=["blocked"],default="blocked")
    a=p.parse_args()
    result=assess(json.loads(a.linkage_report.read_text()),a.expect)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(result["verdict"],result["run_id"],"unverified="+",".join(result["unverified"]))
    return 0 if result["verdict"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
