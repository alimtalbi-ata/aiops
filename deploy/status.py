#!/usr/bin/env python3
"""Read-only AIOps 2.0 stack status and bounded health report.

Never logs Compose environment variables, Docker commands, credentials,
mount contents, container logs or request headers. Uses the selected isolated
project only; never scans/restarts/removes legacy containers.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request

try:
    from plan_isolation import IsolationError, read_env
except ImportError:
    # Supports importlib-based contract tests with deploy in sys.path.
    from deploy.plan_isolation import IsolationError, read_env


def parse_compose_ps(output: str) -> list[dict]:
    if not output.strip():
        return []
    try:
        document = json.loads(output)
        raw = document if isinstance(document, list) else [document]
    except json.JSONDecodeError:
        raw = [json.loads(line) for line in output.splitlines() if line.strip()]
    if not all(isinstance(item, dict) for item in raw):
        raise ValueError("unexpected_compose_ps_schema")
    return raw


def classify_service(entry: dict, expected_project: str) -> dict:
    # Docker Compose versions differ in key casing; output is intentionally filtered.
    name = str(entry.get("Name") or entry.get("name") or "")
    service = str(entry.get("Service") or entry.get("service") or "")
    project = str(entry.get("Project") or entry.get("project") or "")
    state = str(entry.get("State") or entry.get("state") or "UNKNOWN").lower()
    health = str(entry.get("Health") or entry.get("health") or "UNKNOWN").lower()
    exit_code = entry.get("ExitCode", entry.get("exit_code"))
    if not name.startswith(expected_project + "-") or project != expected_project:
        raise ValueError("foreign_container_detected")
    bootstrap = service in ("aiops2-temporal-schema", "aiops2-temporal-namespace")
    if bootstrap:
        condition = "PASS" if state in ("exited", "stopped") and exit_code in (0, "0") else "FAIL"
    elif state != "running":
        condition = "FAIL"
    elif health == "healthy":
        condition = "PASS"
    elif health == "unhealthy":
        condition = "FAIL"
    else:
        condition = "UNKNOWN"
    return {
        "service": service,
        "container": name,
        "state": state,
        "health": health,
        "condition": condition,
        "restart_count": int(entry.get("RestartCount") or entry.get("restart_count") or 0),
    }


def portal_health(port: int, timeout=3.0) -> dict:
    url = f"http://127.0.0.1:{port}/health"
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            if resp.status != 200:
                return {"status": "FAIL", "reason": "non_200_response"}
            data = resp.read(4096)
        parsed = json.loads(data)
        return {"status": "PASS" if parsed.get("status") == "ok" else "UNKNOWN",
                "reported_status": str(parsed.get("status", "unknown"))[:60]}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return {"status": "FAIL", "reason": "portal_health_unreachable_or_invalid"}


def collect(env: dict[str, str], *, execute=subprocess.run, check_portal=True) -> dict:
    stack = env.get("AIOPS_STACK_ID", "")
    if not stack or stack == "aiops2":
        raise ValueError("isolated_stack_id_required")
    report = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "stack_id": stack,
        "mode": "READ_ONLY",
        "live_effects_qualified": False,
        "secrets_in_report": False,
        "services": [],
        "issues": [],
    }
    cmd = ["docker", "compose", "--env-file", ".env", "--project-name", stack,
           "ps", "--all", "--format", "json"]
    try:
        finished = execute(cmd, capture_output=True, text=True, check=False, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        report["issues"].append("docker_compose_inspection_unavailable")
        report["result"] = "UNKNOWN"
        return report
    if finished.returncode:
        report["issues"].append("docker_compose_ps_failed")
        report["result"] = "UNKNOWN"
        return report
    try:
        entries = parse_compose_ps(finished.stdout)
        report["services"] = sorted(
            (classify_service(item, stack) for item in entries),
            key=lambda item: item["service"],
        )
    except (ValueError, TypeError, json.JSONDecodeError):
        report["issues"].append("invalid_or_cross_project_compose_inventory")
        report["result"] = "FAIL"
        return report
    if not report["services"]:
        report["issues"].append("no_services_found")
    for item in report["services"]:
        if item["condition"] == "FAIL":
            report["issues"].append("unhealthy_service:" + item["service"])
        elif item["condition"] == "UNKNOWN":
            report["issues"].append("unverified_service:" + item["service"])
    if check_portal:
        port = env.get("AIOPS_PORTAL_HOST_PORT")
        if not (port and port.isascii() and port.isdecimal() and 1 <= int(port) <= 65535):
            report["portal"] = {"status": "UNKNOWN", "reason": "portal_port_missing"}
        else:
            report["portal"] = portal_health(int(port))
        if report["portal"]["status"] != "PASS":
            report["issues"].append("portal_health_not_confirmed")
    if any(item["condition"] == "FAIL" for item in report["services"]):
        report["result"] = "FAIL"
    elif not report["services"] or report["issues"]:
        report["result"] = "UNKNOWN"
    else:
        report["result"] = "PASS"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, default=Path(".env"))
    parser.add_argument("--report", type=Path, default=Path("reports/stack-status.json"))
    parser.add_argument("--no-health-http", action="store_true")
    args = parser.parse_args(argv)
    try:
        settings = read_env(args.env)
        result = collect(settings, check_portal=not args.no_health_http)
    except (ValueError, IsolationError, OSError, UnicodeError):
        result = {
            "result": "FAIL",
            "mode": "READ_ONLY",
            "issues": ["invalid_environment_or_unavailable_status"],
            "secrets_in_report": False,
        }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("STACK_STATUS=" + result["result"] +
          "|issues=" + str(len(result.get("issues", []))) +
          "|report=" + str(args.report))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
