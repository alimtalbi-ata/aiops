"""V3 isolated synthetic vertical. No network, Docker, host mutations or production ALLOW."""
import argparse
import hashlib
import json

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def execute(event, *, approved=False):
    if type(approved) is not bool:
        raise ValueError("approved must be boolean")
    if not isinstance(event, dict):
        raise ValueError("event must be object")
    for key in ("id", "source", "resource"):
        if not isinstance(event.get(key), str) or not event[key].strip():
            raise ValueError(key + " required")
    if event.get("severity") not in ("warning", "critical"):
        raise ValueError("invalid severity")
    tenant = event.get("tenant", "synthetic-demo")
    if not isinstance(tenant, str) or not tenant.strip():
        raise ValueError("tenant required")
    evidence = {"event_sha256": hashlib.sha256(canonical(event).encode()).hexdigest(), "source": event["source"]}
    incident = {"id": "inc-" + hashlib.sha256(canonical([tenant, event["resource"], event["id"]]).encode()).hexdigest()[:16], "severity": event["severity"], "status": "open"}
    twin = {"resource": event["resource"], "correlation": "same-resource", "evidence": evidence}
    policy = {"decision": "SIMULATE_ONLY" if approved else "DENY", "hitl": "approved_synthetic" if approved else "required"}
    run = {"mode": "SIMULATED", "executed_on_host": False, "status": "simulated" if approved else "blocked"}
    receipt = {"incident_id": incident["id"], "policy": policy["decision"], "run_status": run["status"], "evidence_sha256": evidence["event_sha256"]}
    receipt["sha256"] = hashlib.sha256(canonical(receipt).encode()).hexdigest()
    gamma = {"view": "incident", "incident": incident, "twin": twin, "policy": policy, "run": run, "receipt": receipt}
    return {"contract_version": "v0-synthetic", "tenant": tenant, "event": event, "incident": incident, "twin": twin, "policy": policy, "run": run, "receipt": receipt, "gamma": gamma, "production_authorized": False}

def verify_projection(output):
    """Reject altered synthetic projection; hash is not a signature."""
    if not isinstance(output, dict) or output.get("production_authorized") is not False:
        return False
    try:
        expected = execute(output["event"], approved=output["policy"]["decision"] == "SIMULATE_ONLY")
        return output == expected
    except (KeyError, TypeError, ValueError):
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--approved-synthetic", action="store_true")
    parser.add_argument("--event-file")
    args = parser.parse_args()
    event = json.load(open(args.event_file, encoding="utf-8")) if args.event_file else {"id": "synthetic-001", "source": "synthetic-monitor", "severity": "critical", "resource": "demo-node-01"}
    print(json.dumps(execute(event, approved=args.approved_synthetic), sort_keys=True, indent=2))

if __name__ == "__main__":
    main()
