#!/usr/bin/env python3
"""Plan and verify an isolated AIOps Compose deployment, without changing Docker.

No environment variable VALUES or secrets are emitted in reports. This gate is
safe to run before Docker is installed, during --configure-only, and in CI.
"""
from __future__ import annotations
import argparse
import ipaddress
import json
import re
import socket
import sys
from pathlib import Path

PORT_FIELDS = (
    "AIOPS_PORTAL_HOST_PORT", "AIOPS_GLPI_HOST_PORT",
    "AIOPS_N8N_HOST_PORT", "AIOPS_PROMETHEUS_HOST_PORT",
    "AIOPS_GRAFANA_HOST_PORT", "AIOPS_ALERTMANAGER_HOST_PORT",
)
STACK_RE = re.compile(r"^[a-z][a-z0-9-]{2,28}$")
ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


class IsolationError(ValueError):
    pass


def read_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise IsolationError("environment_file_missing")
    values: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise IsolationError(f"invalid_env_line:{line_number}")
        key, value = line.split("=", 1)
        if not ENV_KEY_RE.fullmatch(key):
            raise IsolationError(f"invalid_env_key:{line_number}")
        if key in values:
            raise IsolationError(f"duplicate_env_key:{key}")
        values[key] = value.strip().strip('"').strip("'")
    return values


def plan(env: dict[str, str], *, expected_stack: str | None = None) -> dict:
    stack_id = env.get("AIOPS_STACK_ID", "")
    if not STACK_RE.fullmatch(stack_id) or stack_id == "aiops2":
        raise IsolationError("unsafe_or_nonisolated_stack_id")
    if expected_stack is not None and stack_id != expected_stack:
        raise IsolationError("requested_stack_identity_mismatch")
    if env.get("COMPOSE_PROJECT_NAME") != stack_id:
        raise IsolationError("compose_project_identity_mismatch")
    raw_ip = env.get("AIOPS_BIND_IP", "")
    try:
        address = ipaddress.ip_address(raw_ip)
    except ValueError as exc:
        raise IsolationError("invalid_bind_address") from exc
    if not address.is_loopback:
        raise IsolationError("nonloopback_bind_not_allowed_in_isolated_mode")
    ports: dict[str, int] = {}
    for key in PORT_FIELDS:
        raw_port = env.get(key, "")
        if not re.fullmatch(r"[0-9]{1,5}", raw_port):
            raise IsolationError("invalid_port:" + key)
        value = int(raw_port)
        if not (1024 <= value <= 65535):
            raise IsolationError("port_out_of_range:" + key)
        if value in ports.values():
            raise IsolationError("duplicate_host_port:" + key)
        ports[key] = value
    return {
        "status": "PASS",
        "mode": "isolated",
        "stack_id": stack_id,
        "compose_project": stack_id,
        "bind": "loopback",
        "ports": ports,
        "network_prefix": stack_id + "-",
        "volume_prefix": stack_id + "-",
        "secrets_in_report": False,
        "legacy_services_touched": False,
    }


def verify_compose(config: dict, report: dict) -> dict:
    stack = report["stack_id"]
    if config.get("name") != stack:
        raise IsolationError("resolved_compose_project_mismatch")
    services = config.get("services")
    if not isinstance(services, dict) or not services:
        raise IsolationError("resolved_services_missing")
    prefixes = {"networks": stack + "-", "volumes": stack + "-"}
    for category, prefix in prefixes.items():
        objects = config.get(category, {})
        if not isinstance(objects, dict):
            raise IsolationError("invalid_compose_" + category)
        for key, obj in objects.items():
            if not isinstance(obj, dict) or obj.get("name", "").startswith(prefix) is False:
                raise IsolationError("unisolated_" + category + ":" + str(key))
            if obj.get("external"):
                raise IsolationError("external_" + category + "_forbidden")
    for name, definition in services.items():
        if not isinstance(definition, dict):
            raise IsolationError("invalid_service:" + name)
        container_name = definition.get("container_name", "")
        if not container_name.startswith(stack + "-"):
            raise IsolationError("unisolated_container:" + name)
        if definition.get("privileged") is True:
            raise IsolationError("privileged_service:" + name)
        if definition.get("network_mode") == "host" or definition.get("pid") == "host":
            raise IsolationError("host_namespace_service:" + name)
        for binding in definition.get("ports") or []:
            if not isinstance(binding, dict):
                raise IsolationError("unrecognized_port_binding:" + name)
            ip = binding.get("host_ip", "")
            try:
                published_address = ipaddress.ip_address(ip)
            except ValueError as exc:
                raise IsolationError("missing_or_invalid_port_bind:" + name) from exc
            if not published_address.is_loopback:
                raise IsolationError("port_published_outside_loopback:" + name)
    return {**report, "resolved_compose_valid": True, "services": len(services),
            "networks": len(config.get("networks", {})),
            "volumes": len(config.get("volumes", {}))}


def probe_ports(report: dict) -> None:
    # This checks availability only: TOCTOU remains possible until Docker binds.
    family = socket.AF_INET6 if ":" in report.get("_bind_ip", "127.0.0.1") else socket.AF_INET
    address = report.get("_bind_ip", "127.0.0.1")
    for label, port in report["ports"].items():
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((address, port))
            except OSError as exc:
                raise IsolationError("host_port_unavailable:" + label) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, default=Path(".env"))
    parser.add_argument("--expected-stack", default=None)
    parser.add_argument("--compose-stdin", action="store_true")
    parser.add_argument("--probe-ports", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        env = read_env(args.env)
        result = plan(env, expected_stack=args.expected_stack)
        if args.compose_stdin:
            result = verify_compose(json.load(sys.stdin), result)
        if args.probe_ports:
            probe_ports({**result, "_bind_ip": env.get("AIOPS_BIND_IP", "")})
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print("ISOLATION_PLAN=PASS|" + json.dumps(result, sort_keys=True))
        return 0
    except (IsolationError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        # Only stable reason codes are logged, never input values.
        print("ISOLATION_PLAN=FAIL|" + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
