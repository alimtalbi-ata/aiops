#!/usr/bin/env python3
"""Read-only comparison of Compose portal publishing with expected public port."""
import argparse
import json
import subprocess
import sys

def analyze(config, expected_port=17777):
    portal = config.get("services", {}).get("aiops2-portal")
    if portal is None:
        return {"status": "BLOCKED", "reason": "portal_service_missing"}
    bindings = []
    for p in portal.get("ports", []):
        if isinstance(p, dict):
            bindings.append({"published": int(p["published"]), "target": int(p["target"])})
        elif isinstance(p, str):
            parts = p.rsplit(":", 2)
            if len(parts) >= 2 and parts[-2].isdigit() and parts[-1].split("/")[0].isdigit():
                bindings.append({"published": int(parts[-2]), "target": int(parts[-1].split("/")[0])})
    matched = any(p["published"] == expected_port for p in bindings)
    return {"status": "PASS" if matched else "BLOCKED",
            "reason": "expected_port_declared" if matched else "expected_port_not_declared",
            "expected_host_port": expected_port, "portal_bindings": bindings,
            "note": "Compose declaration only; does not prove live listener ownership, reachability or authentication"}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-port", type=int, default=17777)
    parser.add_argument("--config-file")
    args = parser.parse_args()
    if args.config_file:
        with open(args.config_file, encoding="utf-8") as f:
            config = json.load(f)
    else:
        proc = subprocess.run(["docker", "compose", "--env-file", ".env", "config", "--format", "json"],
                              capture_output=True, text=True, check=False)
        if proc.returncode:
            print(json.dumps({"status": "BLOCKED", "reason": "compose_config_failed", "stderr_redacted": True}))
            return 2
        config = json.loads(proc.stdout)
    result = analyze(config, args.expected_port)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2

if __name__ == "__main__":
    sys.exit(main())
