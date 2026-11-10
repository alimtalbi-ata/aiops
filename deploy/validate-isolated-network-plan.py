#!/usr/bin/env python3
"""Offline, read-only validator for a proposed DNS-free Docker network plan.

Usage: python3 deploy/validate-isolated-network-plan.py PLAN.json INVENTORY.json
PLAN: {"networks":{"control":"172.30.1.0/24",...},
       "services":{"core":{"control":"172.30.1.10"},...},
       "dependencies":[{"from":"core","to":"postgres"},...]}
INVENTORY: {"routes":["10.0.0.0/8",...],"docker_networks":["172.17.0.0/16",...]}
The inventory must be collected by an authorized operator outside this script.
No network is created or changed by this validator.
"""
import ipaddress
import json
import sys
from pathlib import Path


def validate(plan, inventory):
    errors = []
    if not isinstance(plan, dict) or not isinstance(inventory, dict):
        return ["plan_and_inventory_must_be_objects"]
    nets = plan.get("networks")
    services = plan.get("services")
    deps = plan.get("dependencies")
    routes = inventory.get("routes")
    docker_nets = inventory.get("docker_networks")
    if not isinstance(nets, dict) or not nets or not isinstance(services, dict) or not services:
        return ["missing_networks_or_services"]
    if not isinstance(deps, list) or not isinstance(routes, list) or not isinstance(docker_nets, list):
        return ["missing_dependencies_or_complete_inventory"]
    if not routes or not docker_nets:
        return ["empty_inventory_refused"]
    try:
        parsed = {name: ipaddress.ip_network(cidr, strict=True) for name, cidr in nets.items()}
        occupied = [ipaddress.ip_network(cidr, strict=False) for cidr in routes + docker_nets]\n        # A default route is not an allocated local subnet.\n        occupied = [net for net in occupied if net.prefixlen != 0]
        if any(n.version != 4 for n in list(parsed.values()) + occupied):
            errors.append("ipv4_only")
    except (ValueError, TypeError, AttributeError) as exc:
        return ["invalid_cidr:" + str(exc)]
    names = list(parsed)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if parsed[a].overlaps(parsed[b]):
                errors.append("planned_subnet_overlap:" + a + ":" + b)
        for old in occupied:
            if parsed[a].overlaps(old):
                errors.append("existing_subnet_overlap:" + a + ":" + str(old))
    seen = set()
    for service, attachments in services.items():
        if not isinstance(attachments, dict) or not attachments:
            errors.append("missing_service_networks:" + service)
            continue
        for net, addr in attachments.items():
            if net not in parsed:
                errors.append("unknown_network:" + service + ":" + net)
                continue
            try:
                ip = ipaddress.ip_address(addr)
                if ip not in parsed[net] or ip in (parsed[net].network_address, parsed[net].broadcast_address):
                    errors.append("invalid_attachment_ip:" + service + ":" + net)
                key = (net, str(ip))
                if key in seen:
                    errors.append("duplicate_attachment_ip:" + net + ":" + str(ip))
                seen.add(key)
            except (ValueError, TypeError):
                errors.append("invalid_ip:" + service + ":" + net)
    for dep in deps:
        if not isinstance(dep, dict) or set(dep) != {"from", "to"}:
            errors.append("invalid_dependency")
            continue
        src, dst = dep["from"], dep["to"]
        if src not in services or dst not in services:
            errors.append("unknown_dependency_service:" + str(src) + ":" + str(dst))
        elif not (set(services[src]) & set(services[dst])):
            errors.append("unreachable_dependency:" + src + ":" + dst)
    return errors


def main(argv):
    if len(argv) != 3:
        print("HOLD|usage: validator PLAN.json INVENTORY.json", file=sys.stderr)
        return 2
    try:
        plan = json.loads(Path(argv[1]).read_text())
        inventory = json.loads(Path(argv[2]).read_text())
        errors = validate(plan, inventory)
    except (OSError, ValueError) as exc:
        print("HOLD|input_error:" + str(exc), file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print("HOLD|" + error, file=sys.stderr)
        return 1
    print("NETWORK_PLAN_STATIC_CHECK=PASS|not_runtime_qualification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
