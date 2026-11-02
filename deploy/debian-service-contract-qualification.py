#!/usr/bin/env python3
"""DEV-only automated read-only service contract qualification; never prints tokens."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PORTAL = "aiops2-rebuild-portal"
STATE = Path("/home/aiops/.local/state/aiops-debian-agent")
CHECKS = [
    ("core_incidents", "aiops2-rebuild-core", "", "http://aiops2-core:810/api/incidents"),
    ("core_runs", "aiops2-rebuild-core", "", "http://aiops2-core:810/api/runs"),
    ("core_dashboard", "aiops2-rebuild-core", "", "http://aiops2-core:810/api/dashboard"),
    ("twin_summary", "aiops2-rebuild-twin", "AIOPS_ADMIN_TOKEN", "http://aiops2-twin:811/api/twin/summary"),
    ("twin_graph", "aiops2-rebuild-twin", "AIOPS_ADMIN_TOKEN", "http://aiops2-twin:811/api/twin/graph"),
    ("twin_acme_quality", "aiops2-rebuild-twin", "AIOPS_ADMIN_TOKEN", "http://aiops2-twin:811/api/twin/acme-quality"),
    ("policy_autonomy", "aiops2-rebuild-policy", "AIOPS_INTERNAL_TOKEN", "http://aiops2-policy:813/api/policy/autonomy"),
    ("policy_simulation", "aiops2-rebuild-policy", "AIOPS_INTERNAL_TOKEN", "http://aiops2-policy:813/api/policy/simulation/summary"),
    ("core_hitl", "aiops2-rebuild-core", "ADMIN_TOKEN", "http://aiops2-core:810/api/proposals"),
]
# Tokens only travel through pipes; never through process argv, output or report.
REMOTE = r'''
import json,sys,urllib.request,urllib.error
for name,url,token in json.load(sys.stdin):
    req=urllib.request.Request(url,headers={"Authorization":"Bearer "+token} if token else {})
    try:
        with urllib.request.urlopen(req,timeout=8) as r:
            payload=r.read(1048576)
            try:
                body=json.loads(payload)
                shape="dict" if isinstance(body,dict) else "list" if isinstance(body,list) else "other"
            except (ValueError,UnicodeDecodeError):
                shape="non_json"
            print(json.dumps({"check":name,"http":r.status,"shape":shape}))
    except urllib.error.HTTPError as e:
        print(json.dumps({"check":name,"http":e.code,"shape":"unavailable"}))
    except Exception as e:
        print(json.dumps({"check":name,"http":None,"error":type(e).__name__}))
'''

def token_from(container, key):
    if not key:
        return ""
    p = subprocess.run(
        ["docker", "inspect", container, "--format", "{{range .Config.Env}}{{println .}}{{end}}"],
        capture_output=True, text=True, check=True, timeout=15,
    )
    prefix = key + "="
    return next((line[len(prefix):] for line in p.stdout.splitlines() if line.startswith(prefix)), "")

def main():
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    batch = [(name, url, token_from(container, key)) for name, container, key, url in CHECKS]
    # Fail closed if a protected endpoint has no configured token.
    missing = [name for (name, _, key, _), (_, _, token) in zip(CHECKS, batch) if key and not token]
    if missing:
        raise RuntimeError("missing credentials for: " + ",".join(missing))
    p = subprocess.run(
        ["docker", "exec", "-i", PORTAL, "python", "-c", REMOTE],
        input=json.dumps(batch), text=True, capture_output=True, timeout=110,
    )
    if p.returncode:
        raise RuntimeError("remote qualification failed (exit " + str(p.returncode) + ")")
    results = [json.loads(line) for line in p.stdout.splitlines() if line.strip()]
    if len(results) != len(CHECKS):
        raise RuntimeError("incomplete service qualification")
    success = all(row.get("http") == 200 for row in results)
    receipt = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "host": "SRV-DEB-05",
        "scope": "READ_ONLY_CONTRACTS_NOT_TENANT_E2E",
        "result": "PASS" if success else "FAIL",
        "checks": results,
        "tenant_acl_qualified": False,
        "glpi_write_verified": False,
        "hitl_execution_verified": False,
    }
    dest = STATE / "service-contract-qualification.json"
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(receipt, indent=2) + "\n")
    os.chmod(tmp, 0o600)
    tmp.replace(dest)
    print("SERVICE_CONTRACT_QUALIFICATION_" + receipt["result"])
    for row in results:
        print(row["check"], "HTTP", row.get("http", "ERROR"))
    return 0 if success else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("SERVICE_CONTRACT_QUALIFICATION_ERROR", type(e).__name__, file=sys.stderr)
        sys.exit(2)
