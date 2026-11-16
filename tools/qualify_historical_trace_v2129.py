#!/usr/bin/env python3
"""Fail-closed offline lineage check: historical records, references, and demo policy declarations."""
import argparse
import json
from pathlib import Path

try:
    from tools.summarize_core_historical_v2125 import summarize
    from tools.verify_offline_manifest_v2128 import verify
except ModuleNotFoundError:
    from summarize_core_historical_v2125 import summarize
    from verify_offline_manifest_v2128 import verify


def qualify(run, ledger, evidence, kit):
    summary = summarize(run, ledger, evidence)
    if summary["run_mode"] != "DEMO" or summary["run_status"] != "BLOCKED":
        raise ValueError("historical run is not a blocked demo")
    for collection in ("analyst_evidence", "critic_evidence", "event_evidence"):
        if summary[collection]["missing_from_export"] != 0:
            raise ValueError("missing evidence references: " + collection)
    if not ledger.get("policy_decisions"):
        raise ValueError("missing policy decision records")
    states = summary["policy_decision_states"]
    if set(states) != {"BLOCKED"}:
        raise ValueError("non-blocked policy decision in blocked historical demo")
    manifest_report = verify(Path(kit))
    if manifest_report["mode"] != "OFFLINE_MIXED_SEPARATED":
        raise ValueError("unexpected provenance mode")
    if manifest_report["historical_source"] != "OPERATOR_SUPPLIED_SUMMARY_NOT_INDEPENDENTLY_AUTHENTICATED":
        raise ValueError("unexpected historical provenance")
    return {
        "qualification_version": "2.12.9",
        "status": "PASS",
        "run_id": summary["run_id"],
        "run_mode": summary["run_mode"],
        "run_status": summary["run_status"],
        "evidence_reference_checks": {k: summary[k] for k in (
            "analyst_evidence", "critic_evidence", "event_evidence")},
        "policy_decision_states": states,
        "recorded_critic_validation_declarations": summary["critic_validation_declarations"],
        "offline_manifest_version": manifest_report["manifest_version"],
        "historical_source": manifest_report["historical_source"],
        "dgx_independently_attested": False,
        "live_execution_qualified": False,
        "executor_fencing_qualified": False,
        "interpretation": "Offline consistency of operator-provided records only",
    }


def read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("source missing or symlinked")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("source JSON must be an object")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("run", "ledger", "evidence", "kit"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = None
    try:
        result = qualify(read(args.run), read(args.ledger), read(args.evidence), args.kit)
    except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError) as exc:
        result = {"qualification_version": "2.12.9", "status": "FAIL",
                  "error": str(exc), "dgx_independently_attested": False,
                  "live_execution_qualified": False, "executor_fencing_qualified": False}
    if args.report:
        if args.report.is_symlink():
            raise SystemExit("refusing report symlink")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("AIOPS_V2129_TRACE=" + result["status"])
    if result["status"] != "PASS":
        print(result["error"])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
