"""V3 isolated synthetic vertical. No network, Docker, host mutations or production ALLOW."""
import argparse
import hashlib
import json

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def execute(event, *, approved=False):
    if not isinstance(event, dict):
        raise ValueError("event must be object")
    for key in ("id", "source", "resource"):
        if not isinstance(event.get(key), str) or not event[key].strip():
            raise ValueError(key + " required")
    if event.get("severity") not in ("warning", "critical"):
        raise ValueError("invalid severity")
    evidence = {"event_sha256": hashlib.sha256(canonical(event).encode()).hexdigest(), "source": event["source"]}
    incident = {"id": "inc-" + hashlib.sha256(event["id"].encode()).hexdigest()[:12], "severity": event["severity"], "status": "open"}
    twin = {"resource": event["resource"], "correlation": "same-resource", "evidence": evidence}
    policy = {"decision": "SIMULATE_ONLY" if approved else "DENY", "hitl": "approved_synthetic" if approved else "required"}
    run = {"mode": "SIMULATED", "executed_on_host": False, "status": "simulated" if approved else "blocked"}
    receipt = {"incident_id": incident["id"], "policy": policy["decision"], "run_status": run["status"], "evidence_sha256": evidence["event_sha256"]}
    receipt["sha256"] = hashlib.sha256(canonical(receipt).encode()).hexdigest()
    gamma = {"view": "incident", "incident": incident, "twin": twin, "policy": policy, "run": run, "receipt": receipt}
    return {"event": event, "incident": incident, "twin": twin, "policy": policy, "run": run, "receipt": receipt, "gamma": gamma, "production_authorized": False}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--approved-synthetic", action="store_true")
    parser.add_argument("--event-file")
    args = parser.parse_args()
    event = json.load(open(args.event_file, encoding="utf-8")) if args.event_file else {"id": "synthetic-001", "source": "synthetic-monitor", "severity": "critical", "resource": "demo-node-01"}
    print(json.dumps(execute(event, approved=args.approved_synthetic), sort_keys=True, indent=2))

if __name__ == "__main__":
    main()
