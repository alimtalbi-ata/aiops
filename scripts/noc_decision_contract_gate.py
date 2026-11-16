"""Offline NOC decision contract gate. No network, runtime or remediation effects."""
import json
import sys
from pathlib import Path

REQUIRED = ("mode", "correlation", "impact_path", "evidence", "analyst", "critic", "policy", "next_action")
SAFE_MODES = {"DEMO", "SIMULATION"}
SAFE_ACTIONS = {"OBSERVE", "VERIFY_EVIDENCE", "ESCALATE_HUMAN"}


def validate(snapshot):
    errors = []
    if not isinstance(snapshot, dict):
        return ["SNAPSHOT_NOT_OBJECT"]
    errors.extend("MISSING_" + key.upper() for key in REQUIRED if key not in snapshot)
    if snapshot.get("mode") not in SAFE_MODES:
        errors.append("MODE_NOT_ISOLATED")
    correlation = snapshot.get("correlation")
    if not isinstance(correlation, dict) or not isinstance(correlation.get("alerts"), list) or len(correlation["alerts"]) < 2:
        errors.append("CORRELATION_UNSUPPORTED")
    path = snapshot.get("impact_path")
    if not isinstance(path, list) or path[:1] != ["SAN"] or path[-1:] != ["Payments"] or len(path) < 2:
        errors.append("IMPACT_PATH_UNSUPPORTED")
    evidence = snapshot.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("EVIDENCE_MISSING")
    else:
        for item in evidence:
            if not isinstance(item, dict) or item.get("status") not in ("ATTESTED", "UNKNOWN") or not item.get("source"):
                errors.append("EVIDENCE_PROVENANCE_UNKNOWN")
                break
    for actor in ("analyst", "critic"):
        hypothesis = snapshot.get(actor)
        if not isinstance(hypothesis, dict) or not hypothesis.get("hypothesis") or hypothesis.get("confidence") not in ("UNKNOWN", "LOW", "MEDIUM", "HIGH"):
            errors.append(actor.upper() + "_HYPOTHESIS_MISSING")
    policy = snapshot.get("policy")
    if not isinstance(policy, dict) or policy.get("decision") != "DENY_LIVE" or policy.get("hitl") != "REQUIRED":
        errors.append("POLICY_FAIL_CLOSED_REQUIRED")
    action = snapshot.get("next_action")
    if not isinstance(action, dict) or action.get("type") not in SAFE_ACTIONS or action.get("effect") != "NONE":
        errors.append("ACTION_NOT_READ_ONLY")
    if snapshot.get("live_attested") is True:
        errors.append("LIVE_ATTESTATION_FORBIDDEN")
    return sorted(set(errors))


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: noc_decision_contract_gate.py snapshot.json", file=sys.stderr)
        return 2
    try:
        payload = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "errors": ["INPUT_UNREADABLE"], "detail": type(exc).__name__}))
        return 2
    errors = validate(payload)
    print(json.dumps({"status": "BLOCKED" if errors else "DEMO_CONTRACT_VALID", "errors": errors}, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
