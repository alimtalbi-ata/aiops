#!/usr/bin/env python3
"""Explicit, local-only typed task executor for the EXISTING AIOps2 Docker host.

No network listener, arbitrary shell, remote commands or GitHub polling.
An authenticated transport must be reviewed separately before remote activation.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import time

ALLOWED = {"health", "compose_status", "compose_validate", "service_logs", "deploy_service"}
SERVICE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
SHA = re.compile(r"^[a-f0-9]{40}$")

def validate(task, approved_services):
    if not isinstance(task, dict) or set(task) - {"kind", "service", "sha", "approval"}:
        raise ValueError("invalid task shape")
    kind = task.get("kind")
    if kind not in ALLOWED:
        raise ValueError("unknown task")
    service = task.get("service")
    if kind in {"service_logs", "deploy_service"}:
        if not isinstance(service, str) or not SERVICE.fullmatch(service) or service not in approved_services:
            raise ValueError("service not allowlisted")
    elif service is not None:
        raise ValueError("unexpected service")
    if kind == "deploy_service":
        if not isinstance(task.get("sha"), str) or not SHA.fullmatch(task["sha"]):
            raise ValueError("immutable commit SHA required")
        if task.get("approval") != "operator-approved":
            raise ValueError("deployment requires independent operator approval")
    elif "sha" in task or "approval" in task:
        raise ValueError("unexpected deployment fields")
    return kind

def execute(task, root, approved_services, dry_run=True):
    kind = validate(task, approved_services)
    root = pathlib.Path(root).resolve(strict=True)
    compose = root / "compose.yml"
    if not compose.is_file():
        raise ValueError("compose.yml missing")
    base = ["docker", "compose", "-f", str(compose)]
    commands = {
        "health": ["docker", "info", "--format", "{{.ServerVersion}}"],
        "compose_status": base + ["ps", "--format", "json"],
        "compose_validate": base + ["config", "--quiet"],
    }
    if kind == "service_logs":
        cmd = base + ["logs", "--no-color", "--tail", "100", task["service"]]
    elif kind == "deploy_service":
        # Deliberately fail closed: deploying an arbitrary local checkout does not
        # establish provenance, approval or rollback; transport and SHA binding pending.
        raise ValueError("deployment disabled until signed transport, SHA binding and rollback qualified")
    else:
        cmd = commands[kind]
    if dry_run:
        return {"kind": kind, "dry_run": True, "argv": cmd}
    result = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=60, check=False)
    # Raw stdout/stderr may contain secrets; never serialize them to GitHub.
    return {"kind": kind, "dry_run": False, "exit_code": result.returncode, "ok": result.returncode == 0, "duration_recorded": True}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--services-file", required=True)
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    services = json.loads(pathlib.Path(args.services_file).read_text())
    if not isinstance(services, list) or not all(isinstance(s, str) and SERVICE.fullmatch(s) for s in services):
        raise ValueError("invalid service allowlist")
    task = json.loads(pathlib.Path(args.task_file).read_text())
    print(json.dumps(execute(task, args.root, frozenset(services), not args.execute), sort_keys=True))

if __name__ == "__main__":
    main()
