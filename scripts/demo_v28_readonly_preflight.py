#!/usr/bin/env python3
"""Read-only AIOps2 V28 demo gate. No credentials, mutation, or scheduler changes."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request

SERVICES = ("core", "twin", "policy", "worker", "evidence", "portal",
            "glpi", "temporal", "prometheus", "grafana")
URLS = {
    "portal": "http://127.0.0.1:7777/health",
    "glpi": "http://127.0.0.1:8080/",
    "prometheus": "http://127.0.0.1:9090/-/ready",
    "grafana": "http://127.0.0.1:3000/api/health",
}
EXPECTED_TARGETS = {"aiops2-core", "aiops2-twin", "aiops2-policy",
                    "aiops2-worker", "aiops2-evidence"}


def command(*argv):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=12, check=False)
        return p.returncode, p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""


def http(url, timeout=5):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=timeout) as r:
            return r.status, r.read(500000)
    except urllib.error.HTTPError as e:
        return e.code, b""
    except (OSError, ValueError):
        return 0, b""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=os.path.expanduser("~/aiops2-demo-auto"))
    args = parser.parse_args()
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    checks = []
    def add(name, status, detail):
        checks.append({"name": name, "status": status, "detail": detail})

    for service in SERVICES:
        name = "aiops2-rebuild-" + service
        rc, state = command("docker", "inspect", "--format", "{{.State.Status}}", name)
        add("container:" + service, "PASS" if rc == 0 and state == "running" else "FAIL",
            state if rc == 0 else "unavailable")

    for name, url in URLS.items():
        code, _ = http(url)
        # GLPI can redirect to its login page; this does not attest ticket access.
        good = (200 <= code < 400) if name == "glpi" else code == 200
        add("http:" + name, "PASS" if good else "FAIL", "HTTP " + str(code))

    code, raw = http("http://127.0.0.1:9090/api/v1/targets")
    if code == 200:
        try:
            payload = json.loads(raw)
            targets = payload.get("data", {}).get("activeTargets", [])
            observed = {str(t.get("labels", {}).get("job", "")): t.get("health") for t in targets}
            # Labels can differ across deployments; report actual states without guessing.
            down = sorted(k for k, v in observed.items() if v != "up")
            add("prometheus:targets", "PASS" if targets and not down else "FAIL",
                "active=" + str(len(targets)) + " down=" + ",".join(down))
        except (ValueError, TypeError, AttributeError):
            add("prometheus:targets", "FAIL", "invalid response")
    else:
        add("prometheus:targets", "FAIL", "HTTP " + str(code))

    # Policy is intentionally not probed with a shared token. The previously
    # observed STOP_AUTO is not treated as a fresh safety attestation.
    add("policy:STOP_AUTO", "NOT_TESTED", "authenticated read required; no token exported")
    add("portal:GLPI_ACL", "NOT_TESTED", "fail-closed ACL not qualified")
    add("temporal:workflow", "NOT_TESTED", "running container does not prove workflow execution")
    critical = ("container:core", "container:twin", "container:policy",
                "container:evidence", "container:prometheus", "container:grafana",
                "http:prometheus", "http:grafana", "prometheus:targets")
    failures = [x["name"] for x in checks if x["status"] == "FAIL"]
    verdict = "NO_GO" if any(x in failures for x in critical) else ("GO_DEGRADE" if failures else "GO_DEGRADE")
    # Always degraded until safety and scenario evidence are independently qualified.
    report = {"schema": "aiops2.demo.preflight.v1", "timestamp_utc": now,
              "verdict": verdict, "mode": "READ_ONLY", "checks": checks,
              "notes": ["SYNTHETIC scenarios must be labelled.",
                        "No LIVE remediation or GLPI ticket access attested.",
                        "STOP_AUTO must be verified independently before demo."]}
    out = Path(args.output).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    temp = out / "preflight.json.tmp"
    temp.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    temp.replace(out / "preflight.json")
    text = "\n".join([f"{now} {verdict}"] +
                     [f"{c['status']:11} {c['name']:26} {c['detail']}" for c in checks]) + "\n"
    (out / "preflight.txt").write_text(text)
    print(text, end="")
    return 2 if verdict == "NO_GO" else 0


if __name__ == "__main__":
    sys.exit(main())
