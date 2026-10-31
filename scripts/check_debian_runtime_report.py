#!/usr/bin/env python3
"""Validate a sanitized Debian reporter snapshot from GitHub; never contacts the host."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys

EXPECTED_SCHEMA = 3
EXPECTED_HOST = "SRV-DEB-05"
EXPECTED_AGENT = "aiops-debian-readonly"
REQUIRED_CONTAINERS = (
    "aiops2-rebuild-core",
    "aiops2-rebuild-worker",
    "aiops2-rebuild-policy",
    "aiops2-rebuild-portal",
)
REQUIRED_PUBLISHED_SERVICES = ("portal", "glpi", "grafana", "prometheus", "temporal_ui")


def parse_timestamp(value: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ValueError("collected_at_missing")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("collected_at_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("collected_at_timezone_required")
    return parsed.astimezone(dt.timezone.utc)


def evaluate_report(
    report: dict,
    *,
    now: dt.datetime | None = None,
    max_age_seconds: int = 900,
) -> dict:
    if not isinstance(report, dict):
        raise ValueError("report_object_required")
    if report.get("schema_version") != EXPECTED_SCHEMA:
        raise ValueError("unsupported_report_schema")
    host = report.get("host")
    if not isinstance(host, dict) or host.get("reported_name") != EXPECTED_HOST:
        raise ValueError("unexpected_report_host")
    agent = report.get("agent")
    if not isinstance(agent, dict) or agent.get("name") != EXPECTED_AGENT or agent.get("version") != "1.1.0":
        raise ValueError("unexpected_report_agent")
    collected = parse_timestamp(report.get("collected_at"))
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("validator_clock_timezone_required")
    age = (current.astimezone(dt.timezone.utc) - collected).total_seconds()
    if age < -60:
        raise ValueError("report_timestamp_in_future")
    if age > max_age_seconds:
        raise ValueError("report_stale")

    warnings: list[str] = []
    docker = report.get("docker")
    if not isinstance(docker, dict) or docker.get("available") is not True:
        warnings.append("docker_inventory_unavailable")
        containers = []
    else:
        containers = docker.get("containers", [])
        if not isinstance(containers, list):
            raise ValueError("docker_containers_invalid")
        if docker.get("truncated") is True:
            warnings.append("docker_inventory_truncated")

    container_map = {
        item.get("name"): item
        for item in containers
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    for name in REQUIRED_CONTAINERS:
        item = container_map.get(name)
        if item is None:
            warnings.append("container_not_observed:" + name)
            continue
        if item.get("state") != "running":
            warnings.append("container_not_running:" + name)
        if item.get("health") == "unhealthy":
            warnings.append("container_unhealthy:" + name)

    published = report.get("tcp_published")
    if not isinstance(published, list):
        raise ValueError("tcp_published_required")
    endpoint_map = {
        item.get("service"): item
        for item in published
        if isinstance(item, dict) and isinstance(item.get("service"), str)
    }
    for service in REQUIRED_PUBLISHED_SERVICES:
        item = endpoint_map.get(service)
        if item is None:
            warnings.append("published_endpoint_not_observed:" + service)
        elif item.get("reachable") is not True:
            warnings.append("published_endpoint_unreachable:" + service)

    return {
        "age_seconds": int(max(0, age)),
        "warnings": warnings,
        "snapshot_fresh": True,
        "runtime_observation": "WARN" if warnings else "PASS",
    }


def load_report(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("report_file_missing_or_unsafe")
    if path.stat().st_size > 64 * 1024:
        raise ValueError("report_file_exceeds_size_limit")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("report_json_invalid") from exc
    if not isinstance(payload, dict):
        raise ValueError("report_object_required")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--max-age-seconds", type=int, default=900)
    args = parser.parse_args()
    if not 60 <= args.max_age_seconds <= 3600:
        print("DEBIAN_REPORT=BLOCKED|invalid_max_age", file=sys.stderr)
        return 2
    try:
        result = evaluate_report(load_report(args.report), max_age_seconds=args.max_age_seconds)
    except (ValueError, OSError) as exc:
        reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print("DEBIAN_REPORT=BLOCKED|" + reason, file=sys.stderr)
        return 2
    print("DEBIAN_REPORT=FRESH|age_seconds=" + str(result["age_seconds"]))
    print("DEBIAN_RUNTIME=" + result["runtime_observation"])
    for warning in result["warnings"]:
        print("DEBIAN_RUNTIME_WARNING=" + warning)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
