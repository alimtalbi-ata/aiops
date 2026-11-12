#!/usr/bin/env python3
"""Analyze Debian AIOps2 runtime evidence into prioritized, testable gaps.

Pure offline analysis: no Docker, network, Git or production modifications.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

REQUIRED = {
    "core": "aiops2-rebuild-core",
    "worker": "aiops2-rebuild-worker",
    "portal": "aiops2-rebuild-portal",
    "twin": "aiops2-rebuild-twin",
    "policy": "aiops2-rebuild-policy",
    "evidence": "aiops2-rebuild-evidence",
    "intelligence": "aiops2-rebuild-intelligence",
    "temporal": "aiops2-rebuild-temporal",
    "postgres": "aiops2-rebuild-postgres",
    "glpi": "aiops2-rebuild-glpi",
}
FUNCTIONAL = ("core", "worker", "portal", "policy", "evidence", "intelligence", "temporal", "postgres")
PROBES = ("core", "twin", "evidence", "policy", "worker", "intelligence", "glpi",
          "dashboard", "runs", "incidents", "twin_summary")

def parse_time(value):
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except (TypeError, ValueError):
        return None

def analyze(report, platform=None, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    timestamp = parse_time(report.get("collected_at"))
    gaps = []
    def add(code, severity, evidence, action):
        gaps.append({"code": code, "severity": severity, "evidence": evidence, "next_test": action})
    if timestamp is None:
        add("REPORT_TIMESTAMP_MISSING", "P1", "collected_at absent/invalid", "repair reporter timestamp")
    else:
        age = round((now - timestamp).total_seconds())
        if age > 180:
            add("REPORT_STALE", "P1", f"age_seconds={age}", "check reporter/publisher minute cron")
        if age < -120:
            add("REPORT_CLOCK_SKEW", "P1", f"age_seconds={age}", "check Debian clock and timezone")
    docker = report.get("docker") or {}
    if not docker.get("available"):
        add("DOCKER_UNAVAILABLE", "P0", "docker.available=false", "check Docker access")
    containers = {x.get("name"): x for x in docker.get("containers", []) if isinstance(x, dict)}
    for role, name in REQUIRED.items():
        item = containers.get(name)
        if not item:
            add("MISSING_" + role.upper(), "P0", name, "verify Compose service and image")
        elif item.get("state") != "running":
            add("NOT_RUNNING_" + role.upper(), "P0", f"{name}: {item.get('state')}", "inspect service without deleting data")
        elif item.get("health") == "unhealthy":
            add("UNHEALTHY_" + role.upper(), "P1", name, "inspect health probe and service logs")
        elif role in FUNCTIONAL and item.get("health") == "no-healthcheck":
            add("NO_HEALTHCHECK_" + role.upper(), "P2", name, "qualify functional health endpoint")
    if platform is None:
        add("PLATFORM_GATE_MISSING", "P1", "latest-platform.json absent", "publish hourly platform gate via existing GitHub channel")
    else:
        pt = parse_time(platform.get("utc"))
        if pt is None or (now - pt).total_seconds() > 5400:
            add("PLATFORM_GATE_STALE", "P1", str(platform.get("utc")), "verify H:17 gate execution and publishing")
        if platform.get("verdict") != "PASS":
            add("PLATFORM_GATE_HOLD", "P1", str(platform.get("failures", platform.get("error", "unknown"))), "inspect failing read-only probes")
        for probe in PROBES:
            if (platform.get("probes") or {}).get(probe, {}).get("http") != 200:
                add("PROBE_" + probe.upper(), "P1", str((platform.get("probes") or {}).get(probe)), "repair and rerun service probe")
    # Container health is NOT end-to-end evidence.
    add("E2E_NOT_ATTESTED", "P1", "runtime snapshots do not prove end-to-end execution",
        "run event→Core→Critic→Policy→Temporal/Worker→Evidence→Portal→ITSM and record receipts")
    add("DEPLOY_NOT_ATTESTED", "P1", "no deployment receipt in runtime snapshot",
        "verify poll.sh promotion receipt, image digest and rollback")
    add("CLIENT_INSTALL_NOT_ATTESTED", "P2", "no install qualification in runtime snapshot",
        "exercise clean-room install and restore with versioned manifests")
    priority = {"P0": 0, "P1": 1, "P2": 2}
    gaps.sort(key=lambda x: (priority[x["severity"]], x["code"]))
    return {"schema": "aiops2-gap-analysis-v1", "source_collected_at": report.get("collected_at"),
            "platform_gate_at": (platform or {}).get("utc"), "analyzed_at": now.isoformat(),
            "verdict": "AT_RISK" if gaps else "ON_TRACK", "gaps": gaps}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--platform", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    platform = json.loads(args.platform.read_text()) if args.platform and args.platform.exists() else None
    result = analyze(report, platform)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"{result['verdict']} gaps={len(result['gaps'])} output={args.output}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
