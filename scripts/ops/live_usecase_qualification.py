#!/usr/bin/env python3
"""Read-only recurring AIOps2 use-case qualification on the actual Debian runtime.

Executes installed linkage and platform probes; never creates tickets or approves
actions. HOLD is evidence, not a process crash. Emits a deterministic summary
with specific next engineering actions.
"""
import argparse
import datetime as dt
import json
import re
from pathlib import Path
import subprocess
import sys

RUN_ID="RUN-8CA56A39E58944F1"
PORTAL="aiops2-rebuild-portal"

def portal_probe():
    """Independent Docker inspection; platform gate does not inspect Portal."""
    try:
        p=subprocess.run(["docker","inspect","--format","{{json .State}}",PORTAL],
                         capture_output=True,text=True,timeout=15)
        if p.returncode:
            return {"status":"UNVERIFIED","reason":"DOCKER_INSPECT_FAILED"}
        state=json.loads(p.stdout)
        return {"status":"PASS" if state.get("Status")=="running" and
                state.get("Health",{}).get("Status")!="unhealthy" else "HOLD",
                "state":state.get("Status"),
                "health":state.get("Health",{}).get("Status","NOT_CONFIGURED")}
    except (OSError,ValueError,subprocess.TimeoutExpired):
        return {"status":"UNVERIFIED","reason":"DOCKER_INSPECT_ERROR"}

def invoke(argv, timeout=180):
    try:
        p=subprocess.run(argv,capture_output=True,text=True,timeout=timeout)
        return {"exit":p.returncode,"stderr_tail":p.stderr[-300:]}
    except (OSError,subprocess.TimeoutExpired) as e:
        return {"exit":127,"error":type(e).__name__}

def summarize(linkage, platform, execution, stamp, portal=None, requested_run_id=None):
    checks=linkage.get("checks") or {}
    db=linkage.get("database") or {}
    core=linkage.get("core") or {}
    runtime=platform.get("runtime") or {}
    probes=platform.get("probes") or {}
    portal=portal or {}
    run=(linkage.get("database") or {}).get("run") or {}
    observed_status=str(run.get("status") or (linkage.get("core") or {}).get("run",{}).get("status") or "").upper()
    blocked_safely=(observed_status=="BLOCKED" and
                    checks.get("critic_policy_outbox")=="PASS")

    def check(name, condition, detail, action):
        return {"name":name,"status":"PASS" if condition else "HOLD",
                "evidence":detail,"next_action":None if condition else action}
    # A JSON artifact alone cannot prove that this cycle ran its probes.
    # Exit 2 is a valid HOLD receipt; missing/failed execution stays unverified.
    execution = execution if isinstance(execution, dict) else {}
    execution_checks = []
    for name in ("platform", "linkage"):
        receipt = execution.get(name)
        valid = (isinstance(receipt, dict)
                 and type(receipt.get("exit")) is int
                 and receipt["exit"] in (0, 2)
                 and not receipt.get("error"))
        execution_checks.append(check(
            name + "_probe_execution", valid,
            {"exit": receipt.get("exit") if isinstance(receipt, dict) else None},
            "run the installed " + name + " probe and retain its exit receipt"))
    if requested_run_id is not None:
        records=(linkage, db.get("run"), core.get("run"))
        matches=all(isinstance(record,dict) and record.get("run_id")==requested_run_id
                    for record in records)
        execution_checks.append(check(
            "requested_run_binding", matches, {"requested_run_id":requested_run_id},
            "collect Core and database receipts for the exact requested Run"))
    items=execution_checks + [
        check("core_run_consistency",checks.get("core_run")=="PASS" and checks.get("core_api")=="PASS",
              {"db":checks.get("core_run"),"api":checks.get("core_api")},
              "repair Core run persistence or API parsing"),
        check("evidence_readback",checks.get("evidence_api")=="PASS",
              {"api":checks.get("evidence_api")},"repair Evidence GET /api/runs/{id}/evidence"),
        check("critic_policy_outbox",checks.get("critic_policy_outbox")=="PASS",
              {"outbox":checks.get("critic_policy_outbox")},
              "repair Critic→Policy outbox reconciliation"),
        check("policy_denial_safety",blocked_safely,
              {"run_status":observed_status,"critic_policy_outbox":checks.get("critic_policy_outbox")},
              "verify blocked run status and durable reconciled Policy decision"),
        check("temporal_worker_history",blocked_safely or checks.get("temporal_worker_execution")=="PASS",
              {"history":checks.get("temporal_worker_execution"),
               "applicability":"NOT_APPLICABLE_BLOCKED" if blocked_safely else "REQUIRED"},
              "read Temporal history for an authorized action; never execute a blocked action"),
        check("hitl_action_binding",blocked_safely or checks.get("hitl_action_binding")=="PASS",
              {"binding":checks.get("hitl_action_binding"),
               "applicability":"NOT_APPLICABLE_BLOCKED" if blocked_safely else "REQUIRED"},
              "verify authorization-bound HITL receipt on an approved action, not a denied one"),
        check("itsm_cross_reference",checks.get("glpi_core_link")=="PASS" and checks.get("itsm_readback")=="PASS",
              {"core_link":checks.get("glpi_core_link"),"readback":checks.get("itsm_readback")},
              "reconcile existing GLPI ticket without creating a duplicate"),
        check("platform_smoke",platform.get("verdict")=="PASS",
              {"verdict":platform.get("verdict"),"failures":platform.get("failures",[]),"error":platform.get("error")},
              "fix first failing cross-service probe"),
        check("portal_runtime",portal.get("status")=="PASS",
              portal,"inspect Portal container independently; platform gate does not include Portal"),
        check("intelligence_runtime",runtime.get("aiops2-rebuild-intelligence",{}).get("state")=="running",
              {"state":runtime.get("aiops2-rebuild-intelligence",{}).get("state")},
              "restore Intelligence runtime and qualify Critic decision"),
    ]
    if blocked_safely:
        for item in items:
            if item["name"] in ("temporal_worker_history","hitl_action_binding"):
                item["status"]="NOT_APPLICABLE"
                item["next_action"]="Qualify this chain on a separate approved action run"
    failed=[x["name"] for x in items if x["status"]=="HOLD"]
    return {"schema":"aiops2-live-usecase-qualification-v1","utc":stamp,
            "run_id":requested_run_id or linkage.get("run_id",RUN_ID),
            "requested_run_id":requested_run_id,"read_only":True,
            "verdict":"PASS" if not failed else "HOLD","checks":items,
            "blocking":failed,"probe_execution":execution,
            "interpretation":"A BLOCKED run proves denial safety, not Temporal/HITL execution; approved execution needs a separate run."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--tools",type=Path,default=Path.home()/"aiops2-audit-tools")
    p.add_argument("--output-dir",type=Path,default=Path.home()/"aiops2-release-receipts")
    p.add_argument("--run-id",default=RUN_ID)
    p.add_argument("--observed-glpi-ticket",type=int)
    args=p.parse_args()
    if not re.fullmatch(r"RUN-[A-Z0-9-]{6,80}",args.run_id):
        p.error("invalid run ID")
    if args.observed_glpi_ticket is not None and args.observed_glpi_ticket < 1:
        p.error("ticket must be positive")
    stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.output_dir.mkdir(parents=True,exist_ok=True)
    artifacts={}
    executions={}
    linkage_args=["--run-id",args.run_id]
    if args.observed_glpi_ticket is not None:
        linkage_args.extend(["--observed-glpi-ticket",str(args.observed_glpi_ticket)])
    for name,script,extra in [
        ("platform","platform_readiness_gate.py",[]),
        ("linkage","run_linkage_gate.py",linkage_args)
    ]:
        path=args.output_dir/f"usecase-{name}-{stamp}.json"
        artifacts[name]=path
        executable=args.tools/script
        if not executable.is_file():
            executions[name]={"exit":127,"error":"SCRIPT_NOT_INSTALLED"}
        else:
            executions[name]=invoke([sys.executable,str(executable),*extra,"--output",str(path)])
    def read(name):
        try:
            return json.loads(artifacts[name].read_text())
        except (OSError,ValueError):
            return {}
    result=summarize(read("linkage"),read("platform"),executions,
                     dt.datetime.now(dt.timezone.utc).isoformat(),portal_probe(),requested_run_id=args.run_id)
    out=args.output_dir/f"usecase-summary-{stamp}.json"
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(f"USECASE={result['verdict']} checks={len(result['checks'])} blocking={','.join(result['blocking'])} receipt={out}")
    # Exit 2 means qualification HOLD, not a process crash.
    return 0 if result["verdict"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
